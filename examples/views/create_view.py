"""
Create (or rebuild) a database view in the read-only (RO) SDE database.

Flow per database:
    1. Check the connection is an RO SDE connection.
    2. Preflight: source tables exist, and the view's OBJECTID is unique.
    3. Delete the existing view (if any) and recreate it with
       Create Database View.
    4. If the view has SHAPE: pause so the spatial reference can be set
       and the view registered by hand in ArcGIS Pro Catalog.
    5. Apply field aliases (Alter Fields), grant view privileges
       (Change Privileges), and verify the result.

Why the manual pause: DefineProjection and RegisterWithGeodatabase do
not leave a view with a custom spatial reference (ERROR 000146 or
Unknown) when scripted. In Catalog, for the new view, in this order:
    1. Properties > XY Coordinate System, pick the projection, Apply.
    2. Register With Geodatabase (OBJECTID, SHAPE, POINT).

WARNING: rerunning this script deletes the view, which drops its grants,
spatial reference and registration. Redo the manual steps after a rerun.

Tables in RO are un-versioned, so there are no GDB_ARCHIVE_OID, TODATE
or GDB_IS_DELETE filters in the view definition.
"""

import logging
import sys
import traceback

from configparser import ConfigParser
from datetime import date

from os import (
    environ, getcwd, path
)

import arcpy

import connections

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

log_file = path.join(
    getcwd(),
    f"{date.today()}_create_view.log"
)

logger = logging.getLogger('locators')
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)

file_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

config = ConfigParser()
config.read('config.ini')

# TODO: UPDATE ME
# TASK0330377: HRM-owned/partnered buildings (building points) with civic address attributes.
# VIEW_NAME is a placeholder, confirm the name before running against QA or Prod.
VIEW_NAME = "BLD_building_civic_address_VW"
VIEW_OWNER = "SDEADM"
HAS_GEOMETRY = True
GRANT_TO = "public"

# Tables the view reads from, checked before anything is deleted or created.
SOURCE_TABLES = [
    "SDEADM.LND_CIVIC_ADDRESS",
    "SDEADM.BLD_BUILDING_ASSETPOINT",
]

# Column that must be unique in the view (Esri needs a unique OBJECTID to register it).
UNIQUE_ID_FIELD = "OBJECTID"

# view_definition for Create Database View is the SELECT body only: no
# "CREATE VIEW ... AS", no trailing semicolon, and no ORDER BY (SQL Server
# does not allow it in a view). Keep SQL comments out of the string.
#
# SHAPE and OBJECTID come from BLD_BUILDING_ASSETPOINT (the building points),
# per Lisa O'Toole. LND_CIVIC_ADDRESS only supplies the address attributes.
# The join is one to one (CIV_ID is unique in LND_CIVIC_ADDRESS), so the
# building OBJECTID stays unique. Display names from the original request are
# applied as field aliases (FIELD_ALIASES below) instead of quoted column
# names with spaces.
#
# BL_ID filters (TASK0330377):
#     - The standard selection is ASSETCODE, OWNER/PARTNER and ASSETSTAT.
#     - BL820 and BL320 do not fit it but Recreation wants them, so they are
#       a separate selection (OR) that skips the standard filters.
#     - The NOT IN list is buildings the standard selection picks up that
#       Recreation does not want, and applies to everything.
#
# Duplicate BL_ID values removed from the original NOT IN list:
#     BL938 (listed twice), BL78631 (listed twice)
VIEW_DEFINITION_SQL = """
SELECT
    A.OBJECTID,
    A.SHAPE,
    A.BL_ID,
    A.ASSETCODE,
    A.FAC_NAME,
    A.OWNER,
    A.MAINTBY,
    A.PARTNER,
    A.CONST_YEAR,
    A.TOTAL_SQFT,
    C.PID,
    C.CIV_ID,
    CAST(
        CONCAT_WS(
            ' ',
            NULLIF(LTRIM(RTRIM(C.FULL_CIVIC)), ''),
            NULLIF(LTRIM(RTRIM(C.STR_NAME)), ''),
            NULLIF(LTRIM(RTRIM(C.STR_TYPE)), '')
        ) AS varchar(255)
    ) AS ADDRESS,
    C.GSA_NAME AS COMMUNITY,
    C.DISTRICT,
    A.COMMENTS
FROM SDEADM.BLD_BUILDING_ASSETPOINT A
INNER JOIN SDEADM.LND_CIVIC_ADDRESS C
    ON A.CIV_ID = C.CIV_ID
WHERE (
        (
            A.ASSETCODE IN ('COR', 'AAC')
            AND (A.OWNER = 'HRM' OR A.PARTNER = 'HRM')
            AND A.ASSETSTAT = 'INS'
        )
        OR A.BL_ID IN ('BL820', 'BL320')
    )
  AND A.BL_ID NOT IN ('BL938', 'BL78631', 'BL772', 'BL601', 'BL849', 'BL108', 'BL939')
""".strip()

# Display names from the original request. Fields not listed keep their current alias.
FIELD_ALIASES = {
    "OWNER": "Owner",
    "MAINTBY": "Maintained By",
    "PARTNER": "Partner",
    "CONST_YEAR": "Year of Construction",
    "TOTAL_SQFT": "Total SqFt",
    "ADDRESS": "Address",
    "COMMUNITY": "Community",
    "DISTRICT": "District",
    "COMMENTS": "Comments",
}

# arcpy Field.type -> Alter Fields field_type
ALTER_FIELD_TYPES = {
    "String": "TEXT",
    "SmallInteger": "SHORT",
    "Integer": "LONG",
    "BigInteger": "BIGINTEGER",
    "Single": "FLOAT",
    "Double": "DOUBLE",
    "Date": "DATE",
    "DateOnly": "DATEONLY",
    "TimeOnly": "TIMEONLY",
    "TimestampOffset": "TIMESTAMPOFFSET",
    "GUID": "GUID",
}

SKIP_FIELD_TYPES = ("OID", "Geometry")


def sql_scalar_row(db: str, sql: str):
    """Run sql against db and return the first row as a list, or None."""

    sde_connection = arcpy.ArcSDESQLExecute(db)
    result = sde_connection.execute(sql)

    if isinstance(result, list) and result:
        row = result[0]
        return list(row) if isinstance(row, (list, tuple)) else [row]

    return None


def preflight(db: str, view_sql: str) -> int:
    """
    Check the source tables exist and the unique id field is unique.
    Returns the number of rows the view will have. Raises ValueError on a problem.
    """

    for table in SOURCE_TABLES:
        table_path = path.join(db, table)

        if not arcpy.Exists(table_path):
            raise ValueError(f"Source table '{table}' does not exist in {db}.")

    row = sql_scalar_row(
        db,
        f"SELECT COUNT(*), COUNT(DISTINCT {UNIQUE_ID_FIELD}) FROM ({view_sql}) AS v"
    )

    if row is None:
        raise ValueError("Preflight count query returned no rows.")

    row_count, distinct_ids = row

    logger.info(f"Preflight: {row_count} rows, {distinct_ids} distinct {UNIQUE_ID_FIELD} values.")

    if row_count == 0:
        raise ValueError("The view definition returns no rows. Check the filters.")

    if row_count != distinct_ids:
        raise ValueError(
            f"{UNIQUE_ID_FIELD} is not unique ({row_count - distinct_ids} duplicates). "
            f"More than one building likely shares a civic address, so the view "
            f"cannot be registered with {UNIQUE_ID_FIELD} from LND_CIVIC_ADDRESS."
        )

    return int(row_count)


def delete_view_if_exists(db: str, view_path: str):
    """Delete the view with arcpy (not DROP VIEW) so geodatabase metadata is cleaned up."""

    if arcpy.Exists(view_path):
        arcpy.management.Delete(view_path)
        logger.info(f"Deleted existing view: {view_path}")

    else:
        logger.info("No existing view to delete.")

    arcpy.management.ClearWorkspaceCache(db)


def create_view(db: str, view_name: str, view_sql: str):
    """Create the database view. Create Database View does not register it."""

    arcpy.management.CreateDatabaseView(
        input_database=db,
        view_name=view_name,
        view_definition=view_sql,
    )

    arcpy.management.ClearWorkspaceCache(db)
    logger.info(f"Created view: {view_name}")


def pause_for_manual_registration(view_path: str):
    """Pause so the spatial reference and registration can be done in Catalog."""

    print(
        f"\nMANUAL STEPS for {view_path}, in this order:\n"
        f"  1. Properties > XY Coordinate System, set the projection, Apply.\n"
        f"  2. Register With Geodatabase (OBJECTID, SHAPE, POINT).\n"
    )

    input("Press Enter once the view is registered to continue (aliases, grants)...")

    arcpy.management.ClearWorkspaceCache(path.dirname(view_path))


def build_field_description(view_path: str, field_aliases: dict) -> str:
    """
    Build an Alter Fields field_description from the view's real fields.

    Alter Fields needs each field's actual current type and length, since
    '#' is treated as a change attempt and fails on populated tables.
    Fields without an entry in field_aliases keep their current alias.
    """

    descriptions = []

    for field in arcpy.ListFields(view_path):

        if field.type in SKIP_FIELD_TYPES:
            continue

        field_type = ALTER_FIELD_TYPES.get(field.type)

        if not field_type:
            logger.warning(f"Skipping '{field.name}', unsupported type '{field.type}'.")
            continue

        alias = field_aliases.get(field.name, field.aliasName or field.name)
        length = field.length if field_type == "TEXT" else "#"

        descriptions.append(f"{field.name} # '{alias}' {field_type} {length} # #")

    return "; ".join(descriptions)


def alter_view_aliases(view_path: str, field_aliases: dict):
    """Apply field aliases to the view with Alter Fields (multiple)."""

    missing = [name for name in field_aliases if name not in [f.name for f in arcpy.ListFields(view_path)]]

    if missing:
        logger.warning(f"Aliases defined for fields not in the view: {', '.join(missing)}")

    arcpy.management.AlterFields(
        in_table=view_path,
        field_description=build_field_description(view_path, field_aliases),
    )

    logger.info("Aliases updated.")


def grant_view_privileges(view_path: str, user: str):
    """Grant view privileges. Recreating a view drops grants, so this runs on every rebuild."""

    arcpy.management.ChangePrivileges(
        in_dataset=view_path,
        user=user,
        View="GRANT",
        Edit="AS_IS",
    )

    logger.info(f"Granted view privileges to {user}.")


def verify_view(view_path: str, expected_rows: int):
    """Log the row count and spatial reference, and flag anything that looks wrong."""

    row_count = int(arcpy.management.GetCount(view_path)[0])

    if row_count != expected_rows:
        logger.error(f"Row count mismatch: view has {row_count}, expected {expected_rows}.")

    else:
        logger.info(f"Row count OK: {row_count}.")

    if HAS_GEOMETRY:
        spatial_reference = arcpy.Describe(view_path).spatialReference.name

        if spatial_reference == "Unknown":
            logger.error("Spatial reference is Unknown. Redo the manual Catalog steps.")

        else:
            logger.info(f"Spatial reference: {spatial_reference}")


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    for dbs in [

        [config.get(run_from, "dev_ro")],

        # [config.get(run_from, "qa_ro")],
        # [config.get(run_from, "prod_ro")],
    ]:

        if dbs:
            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for db in dbs:
                logger.info(f"DATABASE: {db}")

                db_type, db_rights = connections.connection_type(db)

                if (db_type, db_rights) != ("SDE", "RO"):
                    logger.warning(f"{db} is not an RO SDE connection. Skipping...")
                    continue

                view_path = path.join(db, f"{VIEW_OWNER}.{VIEW_NAME}")

                try:
                    expected_rows = preflight(db, VIEW_DEFINITION_SQL)

                    delete_view_if_exists(db, view_path)
                    create_view(db, VIEW_NAME, VIEW_DEFINITION_SQL)

                    if HAS_GEOMETRY:
                        pause_for_manual_registration(view_path)

                    alter_view_aliases(view_path, FIELD_ALIASES)
                    grant_view_privileges(view_path, GRANT_TO)
                    verify_view(view_path, expected_rows)

                except ValueError as e:
                    logger.error(f"Preflight failed, nothing was changed: {e}")
                    sys.exit()

                except arcpy.ExecuteError:
                    logger.error(arcpy.GetMessages(2))

                except Exception as e:
                    logger.error(e)
                    tb = sys.exc_info()[2]
                    tbinfo = traceback.format_tb(tb)[0]
                    logger.error("PYTHON ERRORS:\n" + tbinfo + "\n" + str(sys.exc_info()))
                    logger.error("GP ERRORS:\n" + arcpy.GetMessages(2))
                    sys.exit()
