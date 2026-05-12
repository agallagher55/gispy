"""
locks.py — Identify and manage ArcSDE schema locks on feature classes.

Functions
---------
list_locked_features   Scan a workspace and return features that cannot acquire a schema lock.
get_lock_details       Return per-session lock info using arcpy.ListUsers + SQL Server DMVs.
locks_from_services    Filter lock details to sessions whose ClientType is "ArcGIS Server".
remove_locks           Disconnect SDE users holding locks, optionally limited to service sessions.

Notes
-----
Designed for ArcGIS Enterprise Geodatabase on SQL Server.
get_lock_details combines arcpy.ListUsers() (for SDE session metadata including ClientType)
with sys.dm_tran_locks (for table-level lock data) rather than the SDE system tables
(sde.process_information etc.) which are not present in all SQL Server configurations.
"""

import sys
import traceback
import datetime
import os
import logging

import arcpy
from configparser import ConfigParser
from os import environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read("config.ini")

run_from = "SERVER" if "APP" in environ.get("COMPUTERNAME", "") else "LOCAL"

log_file = os.path.join(os.getcwd(), f"{datetime.date.today()}_locks.log")

logger = logging.getLogger("locks")
logger.setLevel(logging.DEBUG)

_fh = logging.FileHandler(log_file)
_fh.setLevel(logging.INFO)
_ch = logging.StreamHandler()
_ch.setLevel(logging.DEBUG)

_fmt = logging.Formatter(
    "%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
_fh.setFormatter(_fmt)
_ch.setFormatter(_fmt)
logger.addHandler(_fh)
logger.addHandler(_ch)


def list_locked_features(workspace: str) -> list[str]:
    """
    Return every feature class / table in *workspace* that currently holds a
    schema lock (i.e. ``arcpy.TestSchemaLock`` returns False).

    Parameters
    ----------
    workspace : str
        Path to an SDE connection file or file geodatabase.

    Returns
    -------
    list[str]
        Fully-qualified paths of locked datasets.
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

    logger.info(f"  {len(all_items)} items found — testing schema locks...")

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


def get_lock_details(sde_workspace: str) -> list[dict]:
    """
    Return detailed lock information for all currently connected SDE sessions.

    Combines ``arcpy.ListUsers()`` (SDE session metadata) with the SQL Server
    ``sys.dm_tran_locks`` DMV (table-level lock data).  The two sources are
    joined on ``login_name`` / username.

    Each returned dict contains:

    ``sde_id``       – SDE connection ID (from arcpy.ListUsers)
    ``username``     – database login name
    ``client_name``  – connecting machine name
    ``client_type``  – ArcGIS client type (e.g. "ArcMap", "ArcGIS Server")
    ``minutes``      – minutes the session has been connected
    ``transactions`` – open transaction count
    ``table_name``   – locked SQL Server object name (None if no table lock)
    ``lock_type``    – SQL Server lock request mode (None if no table lock)
    ``is_service``   – True when client_type is "ArcGIS Server"

    Parameters
    ----------
    sde_workspace : str
        Path to an SDE connection file.  Requires VIEW SERVER STATE permission
        on SQL Server to read sys.dm_tran_locks.

    Returns
    -------
    list[dict]
    """
    logger.info(f"Querying lock details for: {sde_workspace}")

    # --- Part 1: SDE session list via arcpy ----------------------------------
    try:
        sde_users = arcpy.ListUsers(sde_workspace)
    except Exception as e:
        logger.error(f"arcpy.ListUsers failed: {e}")
        sde_users = []

    if not sde_users:
        logger.info("  No active SDE sessions found.")
        return []

    logger.info(f"  {len(sde_users)} active SDE session(s).")

    # --- Part 2: Table-level locks from SQL Server DMVs ----------------------
    # sys.dm_tran_locks is always available on SQL Server and does not depend
    # on any SDE system table existing.
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

    # Build a lookup: {login_name_lower -> [(table_name, lock_type), ...]}
    lock_map: dict[str, list[tuple]] = {}
    try:
        conn = arcpy.ArcSDESQLExecute(sde_workspace)
        raw = conn.execute(sql)

        if raw:
            # ArcSDESQLExecute returns a bare list for a single row
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

    # --- Part 3: Combine -----------------------------------------------------
    results = []
    for user in sde_users:
        username_lower = (user.Name or "").lower()
        user_locks = lock_map.get(username_lower, [(None, None)])

        for table_name, lock_type in user_locks:
            results.append({
                "sde_id": user.ID,
                "username": user.Name,
                "client_name": user.ClientName,
                "client_type": user.ClientType,
                "minutes": user.MinutesConnected,
                "transactions": user.TransactionCount,
                "table_name": table_name,
                "lock_type": lock_type,
                "is_service": user.ClientType == "ArcGIS Server",
            })

    logger.info(f"  {len(results)} session/lock row(s) compiled.")
    return results


def locks_from_services(sde_workspace: str) -> list[dict]:
    """
    Return only lock-detail rows whose ``client_type`` is ``"ArcGIS Server"``.

    Parameters
    ----------
    sde_workspace : str
        Path to an SDE connection file.

    Returns
    -------
    list[dict]
        Subset of :func:`get_lock_details` where ``is_service`` is True.
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


def remove_locks(
    sde_workspace: str,
    services_only: bool = False,
    dry_run: bool = True,
) -> list:
    """
    Disconnect SDE users that are currently holding locks.

    Parameters
    ----------
    sde_workspace : str
        Path to an SDE connection file with DBA / sde-owner privileges.
    services_only : bool
        When True, only disconnect sessions where ``client_type`` is
        ``"ArcGIS Server"``.  When False (default), disconnect *all*
        sessions that hold at least one table lock.
    dry_run : bool
        When True (default) log what *would* be disconnected without
        calling ``arcpy.DisconnectUser``.  Set to False to act.

    Returns
    -------
    list
        arcpy user objects that were (or would be) disconnected.
    """
    lock_details = get_lock_details(sde_workspace)

    # Deduplicate to one entry per SDE ID, keeping only sessions with a lock
    seen_ids: set = set()
    candidates = []
    for row in lock_details:
        if row["table_name"] and row["sde_id"] not in seen_ids:
            if not services_only or row["is_service"]:
                seen_ids.add(row["sde_id"])
                candidates.append(row)

    if not candidates:
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

    # arcpy.DisconnectUser accepts the user objects returned by arcpy.ListUsers
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

    logger.info(f"Disconnected {len(disconnected)}/{len(users_to_disconnect)} session(s).")
    return disconnected


if __name__ == "__main__":

    SDE_RW = config.get(run_from, "dev_rw")
    # SDE_RW = config.get(run_from, "qa_rw")
    # SDE_RW = config.get(run_from, "prod_rw")

    # --- 1. List locked features -------------------------------------------
    locked_features = list_locked_features(SDE_RW)

    if locked_features:
        print(f"\nLocked features ({len(locked_features)}):")
        for f in locked_features:
            print(f"  {f}")
    else:
        print("\nNo locked features found.")

    # --- 2. Full lock details (all sessions) --------------------------------
    lock_info = get_lock_details(SDE_RW)
    print(f"\nActive SDE sessions with lock details: {len(lock_info)}")
    for info in lock_info:
        print(
            f"  sde_id={info['sde_id']}  user={info['username']}"
            f"  machine={info['client_name']}  type={info['client_type']}"
            f"  table={info['table_name']}  service={info['is_service']}"
        )

    # --- 3. Locks from services only ----------------------------------------
    service_lock_info = locks_from_services(SDE_RW)

    # --- 4. Remove locks (dry_run=True by default — set False to act) -------
    removed = remove_locks(SDE_RW, services_only=False, dry_run=True)
    print(f"\nSessions that would be disconnected: {[r['sde_id'] for r in removed]}")
