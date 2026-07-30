"""
locks.py - Identify and manage ArcSDE schema locks on feature classes.

Functions
---------
check_for_locks    Quick single-feature schema lock test (arcpy.TestSchemaLock).
list_locked_features   Scan a workspace and return every feature/table that is locked.
get_lock_details    Per-session lock info: arcpy.ListUsers + SQL Server sys.dm_tran_locks.
get_feature_locks   Lock detail narrowed to a single feature class or table.
locks_from_services     Filter lock details to sessions whose client_type is "ArcGIS Server".
remove_locks        Disconnect only the SDE sessions confirmed to hold a lock.

Notes
-----
Designed for ArcGIS Enterprise Geodatabase on SQL Server. get_lock_details and
get_feature_locks combine arcpy.ListUsers() (session metadata, including
client_type) with sys.dm_tran_locks (table-level lock data) rather than SDE
system tables, since those aren't present in every SQL Server configuration.

get_lock_details/get_feature_locks require VIEW SERVER STATE permission on
SQL Server to read sys.dm_tran_locks. If that permission is missing, the SQL
query fails, is logged as a warning, and lock detail rows come back without
a matched table_name, which means remove_locks() may find nothing to
disconnect even though a schema lock is genuinely held. remove_locks() falls
back to disconnecting every connected session in that case, see its
docstring for details.

Logging: this module does not configure its own handlers. It uses a
placeholder logger (logging.getLogger(__name__)) that the importing script
should overwrite with its own configured logger, e.g.:

    import locks
    locks.logger = logger
"""

import os
import sys
import traceback
import logging

import arcpy

logger = logging.getLogger(__name__)


def check_for_locks(fc_path):
    """Check whether a feature class is free of blocking locks.

    Attribute rule edits require a schema lock, so this tests whether one
    could be acquired rather than modifying anything on the dataset. This
    is a fast, single-item check; use list_locked_features() to scan an
    entire workspace, or get_feature_locks() for who/what is holding the
    lock on a specific feature.

    Args:
        fc_path (str): Full path to the feature class.

    Returns:
        bool: True if no blocking lock was found, False otherwise.
    """
    has_no_lock = arcpy.TestSchemaLock(fc_path)

    if not has_no_lock:
        logger.warning(f"Lock detected on {fc_path}, skipping.")

    return has_no_lock


def list_locked_features(workspace):
    """Return every feature class/table in a workspace that is locked.

    Args:
        workspace (str): Path to an SDE connection file or file geodatabase.

    Returns:
        list[str]: Fully-qualified paths of locked datasets.
    """
    logger.info(f"Scanning workspace for locked features: {workspace}")
    locked = []

    with arcpy.EnvManager(workspace=workspace):
        features = arcpy.ListFeatureClasses() or []
        tables = arcpy.ListTables() or []
        datasets = arcpy.ListDatasets() or []

        for ds in datasets:
            features.extend(arcpy.ListFeatureClasses(feature_dataset=ds) or [])

        all_items = features + tables

    logger.info(f"  {len(all_items)} items found, testing schema locks...")

    for item in all_items:
        full_path = os.path.join(workspace, item)
        try:
            if not arcpy.TestSchemaLock(full_path):
                logger.info(f"  LOCKED: {item}")
                locked.append(full_path)

        except arcpy.ExecuteError:
            logger.error(f"  Error testing lock on {item}: {arcpy.GetMessages(2)}")
        except Exception as e:
            logger.error(f"  Unexpected error on {item}: {e}")

    logger.info(f"  {len(locked)} locked feature(s) found.")
    return locked


def get_lock_details(sde_workspace):
    """Return detailed lock information for all connected SDE sessions.

    Combines arcpy.ListUsers() (SDE session metadata) with the SQL Server
    sys.dm_tran_locks DMV (table-level lock data), joined on login_name.

    Each returned dict contains:
        sde_id, username, client_name, client_type, minutes, transactions,
        table_name (None if no table lock resolved), lock_type (None if no
        table lock resolved), is_service (True when client_type is
        "ArcGIS Server").

    Args:
        sde_workspace (str): Path to an SDE connection file. Requires
            VIEW SERVER STATE permission on SQL Server to read
            sys.dm_tran_locks.

    Returns:
        list[dict]
    """
    logger.info(f"Querying lock details for: {sde_workspace}")

    try:
        sde_users = arcpy.ListUsers(sde_workspace)

    except Exception as e:
        logger.error(f"arcpy.ListUsers failed: {e}")
        sde_users = []

    if not sde_users:
        logger.info("  No active SDE sessions found.")
        return []

    logger.info(f"  {len(sde_users)} active SDE session(s).")

    sql = """
        SELECT
            s.login_name,
            s.host_name,
            o.name          AS table_name,
            tl.request_mode AS lock_type
        FROM
            sys.dm_exec_sessions  AS s
        JOIN
            sys.dm_tran_locks     AS tl ON s.session_id = tl.request_session_id
        LEFT JOIN
            sys.objects           AS o  ON tl.resource_associated_entity_id = o.object_id
        WHERE
            tl.resource_database_id = DB_ID()
            AND tl.resource_type    = 'OBJECT'
        ORDER BY
            s.login_name
    """

    lock_map = {}
    try:
        conn = arcpy.ArcSDESQLExecute(sde_workspace)
        raw = conn.execute(sql)

        if raw:
            if not isinstance(raw[0], list):
                raw = [raw]

            for login_name, host_name, table_name, lock_type in raw:
                key = (login_name or "").lower()
                lock_map.setdefault(key, []).append((table_name, lock_type))

    except Exception as e:
        logger.warning(
            f"  Could not query sys.dm_tran_locks (check VIEW SERVER STATE "
            f"permission): {e}\n  Continuing without table-level lock data."
        )

    results = []
    for user in sde_users:
        username_lower = (user.Name or "").lower()
        user_locks = lock_map.get(username_lower, [(None, None)])
        client_type = getattr(user, "ClientType", None)

        for table_name, lock_type in user_locks:
            results.append({
                "sde_id": user.ID,
                "username": user.Name,
                "client_name": user.ClientName,
                "client_type": client_type,
                "minutes": user.MinutesConnected,
                "transactions": user.TransactionCount,
                "table_name": table_name,
                "lock_type": lock_type,
                "is_service": client_type == "ArcGIS Server",
            })

    logger.info(f"  {len(results)} session/lock row(s) compiled.")
    return results


def get_feature_locks(sde_workspace, feature):
    """Return lock details for a single feature class or table.

    Args:
        sde_workspace (str): Path to an SDE connection file.
        feature (str): Feature class or table name. Can be fully qualified
            ("SDEADM.TRN_bridge") or unqualified ("TRN_bridge").

    Returns:
        list[dict]: Same structure as get_lock_details(). Empty list means
            no locks are held on that feature, or the schema lock test
            already passed.
    """
    full_path = os.path.join(sde_workspace, feature)
    table_name = feature.split(".")[-1]

    schema_locked = not arcpy.TestSchemaLock(full_path)
    logger.info(
        f"Schema lock test for '{feature}': "
        f"{'LOCKED' if schema_locked else 'available'}"
    )

    if not schema_locked:
        return []

    try:
        sde_users = arcpy.ListUsers(sde_workspace)

    except Exception as e:
        logger.error(f"arcpy.ListUsers failed: {e}")
        return []

    sql = f"""
        SELECT
            s.login_name,
            o.name          AS table_name,
            tl.request_mode AS lock_type
        FROM
            sys.dm_exec_sessions  AS s
        JOIN
            sys.dm_tran_locks     AS tl ON s.session_id = tl.request_session_id
        LEFT JOIN
            sys.objects           AS o  ON tl.resource_associated_entity_id = o.object_id
        WHERE
            tl.resource_database_id = DB_ID()
            AND tl.resource_type    = 'OBJECT'
            AND o.name              = '{table_name}'
        ORDER BY
            s.login_name
    """

    lock_map = {}
    try:
        conn = arcpy.ArcSDESQLExecute(sde_workspace)
        raw = conn.execute(sql)

        if raw:
            if not isinstance(raw[0], list):
                raw = [raw]

            for login_name, tbl, lock_type in raw:
                key = (login_name or "").lower()
                lock_map.setdefault(key, []).append((tbl, lock_type))

    except Exception as e:
        logger.warning(
            f"  Could not query sys.dm_tran_locks: {e}\n"
            "  Returning sessions without table-level lock detail."
        )

    results = []
    for user in sde_users:
        username_lower = (user.Name or "").lower()
        user_locks = lock_map.get(username_lower)

        if not user_locks:
            continue

        client_type = getattr(user, "ClientType", None)

        for tbl, lock_type in user_locks:
            results.append({
                "sde_id": user.ID,
                "username": user.Name,
                "client_name": user.ClientName,
                "client_type": client_type,
                "minutes": user.MinutesConnected,
                "transactions": user.TransactionCount,
                "table_name": tbl,
                "lock_type": lock_type,
                "is_service": client_type == "ArcGIS Server",
            })

    if results:
        logger.info(f"  {len(results)} lock(s) found on '{feature}':")
        for row in results:
            logger.info(
                f"    sde_id={row['sde_id']}  user={row['username']}"
                f"  type={row['client_type']}  lock={row['lock_type']}"
            )

    else:
        logger.info(f"  No session-level locks resolved for '{feature}'.")

    return results


def locks_from_services(sde_workspace):
    """Return only lock-detail rows whose client_type is "ArcGIS Server".

    Args:
        sde_workspace (str): Path to an SDE connection file.

    Returns:
        list[dict]: Subset of get_lock_details() where is_service is True.
    """
    all_locks = get_lock_details(sde_workspace)
    service_locks = [row for row in all_locks if row["is_service"]]

    if service_locks:
        logger.info(f"Service-originated locks ({len(service_locks)}):")
        for row in service_locks:
            logger.info(
                f"  sde_id={row['sde_id']}  user={row['username']}"
                f"  machine={row['client_name']}  table={row['table_name']}"
            )

    else:
        logger.info("No service-originated locks detected.")

    return service_locks


def remove_locks(sde_workspace, feature=None, services_only=False, dry_run=True):
    """Disconnect SDE users confirmed to be holding a lock.

    Only sessions matched to an actual table lock (via get_feature_locks()
    or get_lock_details()) are targeted, rather than every connected
    session. If a feature is given but no matching lock is found, for
    example because VIEW SERVER STATE permission is missing so the
    underlying SQL query silently returns nothing, this falls back to
    disconnecting every connected session on sde_workspace as a last
    resort, since a lock reported by check_for_locks() must be coming from
    somewhere even if it can't be attributed to a specific session.

    Args:
        sde_workspace (str): Path to an SDE connection file with DBA /
            sde-owner privileges.
        feature (str, optional): Feature class or table name to target.
            When given, only sessions locking that feature are considered.
            When omitted, every locked session in the workspace is
            considered.
        services_only (bool): When True, only disconnect sessions where
            client_type is "ArcGIS Server". Defaults to False.
        dry_run (bool): When True (default), log what would be
            disconnected without calling arcpy.DisconnectUser. Set to
            False to act.

    Returns:
        list: arcpy user objects that were (or would be) disconnected.
    """
    if feature:
        lock_details = get_feature_locks(sde_workspace, feature)
    else:
        lock_details = get_lock_details(sde_workspace)

    seen_ids = set()
    candidates = []
    for row in lock_details:
        if row["table_name"] and row["sde_id"] not in seen_ids:
            if not services_only or row["is_service"]:
                seen_ids.add(row["sde_id"])
                candidates.append(row)

    if not candidates:
        if feature:
            logger.warning(
                f"No session could be matched to a lock on '{feature}'. "
                f"Falling back to disconnecting all sessions on "
                f"{sde_workspace}."
            )
            return _disconnect_all(sde_workspace, dry_run)

        logger.info("No matching locked sessions to remove.")
        return []

    prefix = "[DRY RUN] Would disconnect" if dry_run else "Disconnecting"
    logger.info(f"{prefix} {len(candidates)} session(s):")
    for row in candidates:
        logger.info(
            f"  sde_id={row['sde_id']}  user={row['username']}"
            f"  machine={row['client_name']}  type={row['client_type']}"
            f"  table={row['table_name']}"
        )

    if dry_run:
        return candidates

    try:
        sde_users = arcpy.ListUsers(sde_workspace)

    except Exception as e:
        logger.error(f"arcpy.ListUsers failed: {e}")
        return []

    target_ids = {row["sde_id"] for row in candidates}
    users_to_disconnect = [u for u in sde_users if u.ID in target_ids]

    disconnected = []
    for user in users_to_disconnect:
        try:
            arcpy.DisconnectUser(sde_workspace, user)
            logger.info(f"  Disconnected sde_id={user.ID}  user={user.Name}")
            disconnected.append(user)

        except arcpy.ExecuteError:
            logger.error(
                f"  Failed to disconnect sde_id={user.ID}: {arcpy.GetMessages(2)}"
            )
        except Exception as e:
            logger.error(f"  Unexpected error disconnecting sde_id={user.ID}: {e}")
            tb = sys.exc_info()[2]
            logger.error("PYTHON ERRORS:\n" + traceback.format_tb(tb)[0])

    logger.info(
        f"Disconnected {len(disconnected)}/{len(users_to_disconnect)} session(s)."
    )
    return disconnected


def _disconnect_all(sde_workspace, dry_run):
    """Fallback: disconnect every connected session on a workspace.

    Only called from remove_locks() when a targeted disconnect couldn't be
    resolved to a specific session. Not intended to be called directly.

    Args:
        sde_workspace (str): Path to an SDE connection file.
        dry_run (bool): When True, log what would be disconnected without
            acting.

    Returns:
        bool: True if the disconnect succeeded (or would, in dry run),
            False otherwise.
    """
    if dry_run:
        logger.info(f"[DRY RUN] Would disconnect all users on {sde_workspace}")
        return True

    try:
        arcpy.DisconnectUser(sde_workspace, "ALL")
        logger.info(f"Disconnected all users on {sde_workspace}")
        return True

    except arcpy.ExecuteError:
        logger.error(
            f"Failed to disconnect users on {sde_workspace}: "
            f"{arcpy.GetMessages(2)}"
        )
        return False


if __name__ == "__main__":
    from configparser import ConfigParser

    config = ConfigParser()
    config.read("config.ini")

    SDE_RW = config.get("SERVER", "dev_rw")

    locked_features = list_locked_features(SDE_RW)

    if locked_features:
        print(f"\nLocked features ({len(locked_features)}):")
        for f in locked_features:
            print(f"  {f}")

    else:
        print("\nNo locked features found.")

    lock_info = get_lock_details(SDE_RW)
    print(f"\nActive SDE sessions with lock details: {len(lock_info)}")
    for info in lock_info:
        print(
            f"  sde_id={info['sde_id']}  user={info['username']}"
            f"  machine={info['client_name']}  type={info['client_type']}"
            f"  table={info['table_name']}  service={info['is_service']}"
        )

    service_lock_info = locks_from_services(SDE_RW)

    removed = remove_locks(SDE_RW, services_only=False, dry_run=True)
    print(f"\nSessions that would be disconnected: {[r['sde_id'] for r in removed]}")
