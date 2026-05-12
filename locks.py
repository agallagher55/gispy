"""
locks.py — Identify and manage ArcSDE schema locks on feature classes.

Functions
---------
list_locked_features   Scan a workspace and return features that cannot acquire a schema lock.
get_lock_details       Query SDE system tables for full lock info (user, process, service flag).
locks_from_services    Filter lock details to only rows originating from ArcGIS Server services.
remove_locks           Disconnect SDE users holding locks, optionally limited to service accounts.
"""

import sys
import traceback
import datetime
import os

import arcpy
from configparser import ConfigParser
from os import environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read("config.ini")

run_from = "SERVER" if "APP" in environ.get("COMPUTERNAME", "") else "LOCAL"

log_file = os.path.join(os.getcwd(), f"{datetime.date.today()}_locks.log")

import logging

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


# ---------------------------------------------------------------------------
# Service-account substrings used to flag service-originated locks.
# Extend this list to match your ArcGIS Server account naming conventions.
# ---------------------------------------------------------------------------
SERVICE_ACCOUNT_HINTS = [
    "arcgis",
    "agsservice",
    "agssvc",
    "ags_",
    "_ags",
    "arcgisserver",
]


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
        Fully-qualified names of locked datasets.
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
    Query SDE system tables to return detailed lock information for all
    currently connected sessions.

    Each returned dict contains:

    ``sde_id``      – SDE process ID
    ``pid``         – OS process ID
    ``server``      – client machine name
    ``direct_conn`` – True if the connection is a direct ArcSDE connection
    ``username``    – database login name
    ``table_name``  – locked table (None when the session holds no table lock)
    ``lock_type``   – lock type code (None when no table lock)
    ``is_service``  – True when the username matches a known service-account hint

    Parameters
    ----------
    sde_workspace : str
        Path to an SDE connection file with sufficient privileges to query
        the SDE schema (typically a DBA or sde-owner connection).

    Returns
    -------
    list[dict]
    """
    logger.info(f"Querying SDE lock details for: {sde_workspace}")

    # SDE.PROCESS_INFORMATION joined to SDE.TABLE_LOCKS (LEFT JOIN so we see
    # all sessions, not just those with an active table lock).
    sql = """
        SELECT
            pi.sde_id,
            pi.server_id      AS pid,
            pi.server         AS client_machine,
            pi.direct_connect,
            pi.owner          AS username,
            tl.registration_id,
            obj.table_name,
            tl.lock_type
        FROM
            sde.process_information AS pi
        LEFT JOIN
            sde.table_locks AS tl  ON pi.sde_id = tl.sde_id
        LEFT JOIN
            sde.layers      AS obj ON tl.registration_id = obj.registration_id
        ORDER BY
            pi.sde_id
    """

    try:
        conn = arcpy.ArcSDESQLExecute(sde_workspace)
        raw = conn.execute(sql)
    except Exception as e:
        logger.error(f"Failed to query SDE system tables: {e}")
        return []

    if not raw:
        logger.info("  No active sessions found.")
        return []

    # ArcSDESQLExecute returns a list of lists, or a single list for one row
    if isinstance(raw, list) and raw and not isinstance(raw[0], list):
        raw = [raw]

    results = []
    for row in raw:
        (sde_id, pid, machine, direct, username, reg_id,
         table_name, lock_type) = row

        username_str = (username or "").lower()
        is_service = any(hint in username_str for hint in SERVICE_ACCOUNT_HINTS)

        results.append({
            "sde_id": sde_id,
            "pid": pid,
            "server": machine,
            "direct_conn": bool(direct),
            "username": username,
            "table_name": table_name,
            "lock_type": lock_type,
            "is_service": is_service,
        })

    logger.info(f"  {len(results)} session row(s) returned.")
    return results


def locks_from_services(sde_workspace: str) -> list[dict]:
    """
    Return only the lock-detail rows that appear to originate from ArcGIS
    Server services (matched via :data:`SERVICE_ACCOUNT_HINTS`).

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
                f"  machine={row['server']}  table={row['table_name']}"
            )
    else:
        logger.info("No service-originated locks detected.")

    return service_locks


def remove_locks(
    sde_workspace: str,
    services_only: bool = False,
    dry_run: bool = True,
) -> list[int]:
    """
    Disconnect SDE users that are currently holding locks.

    Parameters
    ----------
    sde_workspace : str
        Path to an SDE connection file with DBA / sde-owner privileges.
    services_only : bool
        When True, only disconnect sessions flagged as ``is_service``.
        When False (default), disconnect *all* locked sessions.
    dry_run : bool
        When True (default) log what *would* be disconnected without
        actually calling ``arcpy.DisconnectUser``.  Set to False to
        perform the disconnection.

    Returns
    -------
    list[int]
        SDE IDs of sessions that were (or would be) disconnected.
    """
    lock_details = get_lock_details(sde_workspace)

    # Keep only sessions that actually hold a table lock
    locked_sessions = [row for row in lock_details if row["table_name"]]

    if services_only:
        locked_sessions = [row for row in locked_sessions if row["is_service"]]

    if not locked_sessions:
        logger.info("No matching locks to remove.")
        return []

    sde_ids = list({row["sde_id"] for row in locked_sessions})

    logger.info(
        f"{'[DRY RUN] Would disconnect' if dry_run else 'Disconnecting'} "
        f"{len(sde_ids)} SDE session(s): {sde_ids}"
    )

    if dry_run:
        for row in locked_sessions:
            logger.info(
                f"  [DRY RUN] sde_id={row['sde_id']}  user={row['username']}"
                f"  machine={row['server']}  table={row['table_name']}"
            )
        return sde_ids

    disconnected = []
    for sde_id in sde_ids:
        try:
            arcpy.DisconnectUser(sde_workspace, sde_id)
            logger.info(f"  Disconnected sde_id={sde_id}")
            disconnected.append(sde_id)
        except arcpy.ExecuteError:
            logger.error(
                f"  Failed to disconnect sde_id={sde_id}: {arcpy.GetMessages(2)}"
            )
        except Exception as e:
            logger.error(f"  Unexpected error disconnecting sde_id={sde_id}: {e}")
            tb = sys.exc_info()[2]
            logger.error("PYTHON ERRORS:\n" + traceback.format_tb(tb)[0])

    logger.info(f"Disconnected {len(disconnected)}/{len(sde_ids)} session(s).")
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
            f"  machine={info['server']}  table={info['table_name']}"
            f"  service={info['is_service']}"
        )

    # --- 3. Locks from services only ----------------------------------------
    service_lock_info = locks_from_services(SDE_RW)

    # --- 4. Remove locks (dry_run=True by default — set False to act) -------
    removed = remove_locks(SDE_RW, services_only=False, dry_run=True)
    print(f"\nSessions that would be disconnected: {removed}")
