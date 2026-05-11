"""
2_create_lrs_feature_class.py

One-time setup script: create the SDE feature classes that LRS_updates.py
writes into via TruncateTable → Append on each scheduled run.

These are plain (non-versioned, non-LRS-event) feature classes that hold the
publishable output of OverlayEvents + query filtering.  They must exist before
LRS_updates.py can populate them.

Workflow per feature
--------------------
1. Run OverlayEvents to build the required segmented intermediate (if missing).
2. Build the publishable query layer (same SQL used by the update script).
3. CopyFeatures → RW SDE  (derives schema + loads initial data in one step).
4. CopyFeatures → RO SDE.
5. Grant PUBLIC VIEW on both.

Adding a new feature
--------------------
1. Define a function that returns a query layer (see _speed_limit_neighbourhood below).
2. Add an entry to FEATURES_TO_CREATE, pointing at:
   - feature_name     : bare name used in both RW and RO connections
   - segmentation_fn  : callable(DynSegFeature) → path to intermediate FC,
                        or None if no OverlayEvents step is needed
   - layer_fn         : callable(DynSegFeature) → in-memory query layer
"""

import os
import sys
import traceback
import logging
import datetime

import arcpy
from configparser import ConfigParser

from LRS_updates import (
    MTM5_SPATIAL_REFERENCE,
    SDE_SPEED_LIMIT_DYN_SEG_FEATURE_NAME,
    SPEED_LIMIT_NEIGHBOURHOOD_FEATURE_NAME,
    DynSegFeature,
    LicenseError,
)

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

# ── Config ────────────────────────────────────────────────────────────────────

config = ConfigParser()
config.read(r"E:\HRM\Scripts\Python\config.ini")

SDEADM_RW = config.get('SDEADM_RW', 'sdeFile')
SDEADM_RO = config.get('SDEADM_RO', 'sdeFile')

# ── Logging ───────────────────────────────────────────────────────────────────

log_file = os.path.join(
    os.getcwd(),
    f"{datetime.date.today()}_create_lrs_feature_class.log"
)

logger = logging.getLogger("create_lrs_fc")
logger.setLevel(logging.DEBUG)

_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s',
    datefmt='%d-%b-%y %H:%M:%S'
)
_file_handler = logging.FileHandler(log_file)
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(_formatter)
_console_handler = logging.StreamHandler()
_console_handler.setLevel(logging.DEBUG)
_console_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)
logger.addHandler(_console_handler)


# ── Query-layer builders ──────────────────────────────────────────────────────

def _speed_limit_neighbourhood_layer(dyn_seg: DynSegFeature):
    """Query layer for TRNLRS_SpeedLimit_Neighbourhood_VW.

    Mirrors the SQL in DynSegFeature.update_speed_limit_neighbourhood so the
    schema and initial data are identical to what the update script produces.
    """
    query = f"""
        SELECT
            e.OBJECTID,
            e.ROUTEID,
            e.STR_NAME,
            e.ROUTENAME AS FULL_NAME,
            e.ST_CLASS,
            e.SPEED,
            e.REVIEW_STAT,
            e.DATE_EFFECTIVE,
            sln.MinAddDate AS ADDDATE,
            sln.AddBy      AS ADDBY,
            sln.MaxModDate AS MODDATE,
            sln.ModBy      AS MODBY,
            e.SHAPE
        FROM {SDE_SPEED_LIMIT_DYN_SEG_FEATURE_NAME} e
        LEFT JOIN (
            SELECT
                ROUTEID,
                MIN(ADDDATE) AS MinAddDate,
                MIN(ADDBY)   AS AddBy,
                MAX(MODDATE) AS MaxModDate,
                MAX(MODBY)   AS ModBy
            FROM SDEADM.E_SpeedLimit
            WHERE TODATE IS NULL
              AND (GDB_IS_DELETE IS NULL OR GDB_IS_DELETE = 0)
            GROUP BY ROUTEID
        ) sln ON e.ROUTEID = sln.ROUTEID
        WHERE e.TO_DATE IS NULL
    """
    return arcpy.MakeQueryLayer_management(
        input_database=dyn_seg.sde_workspace,
        out_layer_name="setup_speed_limit_neighbourhood_layer",
        query=query,
        oid_fields="OBJECTID",
        shape_type="POLYLINE",
        srid="0",
        spatial_reference=MTM5_SPATIAL_REFERENCE,
        m_values="DO_NOT_INCLUDE_M_VALUES",
        z_values="DO_NOT_INCLUDE_Z_VALUES",
    )[0]


# ── Feature registry ──────────────────────────────────────────────────────────
# TODO: add entries here when creating additional dynamically segmented features.
#
# Each entry:
#   feature_name    bare FC name (no schema prefix); used in both RW and RO.
#   segmentation_fn callable(DynSegFeature) that runs OverlayEvents and returns
#                   the intermediate FC path, or None to skip that step.
#   layer_fn        callable(DynSegFeature) that returns an in-memory query
#                   layer whose schema matches the target feature class.

FEATURES_TO_CREATE = [
    {
        "feature_name": SPEED_LIMIT_NEIGHBOURHOOD_FEATURE_NAME,
        "segmentation_fn": lambda ds: ds.update_speed_limit_neighbourhood_segmentation(),
        "layer_fn": _speed_limit_neighbourhood_layer,
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_in_sde(query_layer, feature_name: str, sde_conn: str) -> str:
    """CopyFeatures from query_layer into sde_conn, then grant PUBLIC VIEW."""
    out_path = os.path.join(sde_conn, feature_name)

    if arcpy.Exists(out_path):
        logger.info(f"Already exists, skipping: {out_path}")
        return out_path

    logger.info(f"Creating '{feature_name}' in {sde_conn}...")
    arcpy.CopyFeatures_management(query_layer, out_path)
    logger.info(arcpy.GetMessages())

    arcpy.ChangePrivileges_management(out_path, user="PUBLIC", View="GRANT")
    logger.info(f"Granted PUBLIC VIEW on {out_path}")

    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    start_time = datetime.datetime.now().strftime("%d-%b-%y %H:%M:%S")
    logger.info(f"Start: {start_time}")
    logger.info("-----------------------")

    try:
        if arcpy.CheckExtension("LocationReferencing") == "Available":
            arcpy.CheckOutExtension("LocationReferencing")
            logger.info("Checked out LocationReferencing Extension.")
        else:
            raise LicenseError("Unable to checkout Location Referencing License.")

        dyn_seg = DynSegFeature(sde_workspace=SDEADM_RW)

        for feature_def in FEATURES_TO_CREATE:

            feature_name = feature_def["feature_name"]
            segmentation_fn = feature_def["segmentation_fn"]
            layer_fn = feature_def["layer_fn"]

            logger.info(f"\n{'=' * 60}")
            logger.info(f"Setting up: {feature_name}")
            logger.info(f"{'=' * 60}")

            # Step 1 — build the segmented intermediate if required
            if segmentation_fn:
                logger.info("Running OverlayEvents segmentation...")
                segmentation_fn(dyn_seg)

            # Step 2 — build the publishable query layer
            logger.info("Building query layer...")
            query_layer = layer_fn(dyn_seg)

            row_count = int(arcpy.GetCount_management(query_layer)[0])
            logger.info(f"Query layer row count: {row_count}")

            if row_count == 0:
                logger.warning(
                    f"Query returned 0 rows for '{feature_name}'. "
                    "The feature class will be created but will be empty. "
                    "Verify that the segmented intermediate exists and has data."
                )

            # Step 3 — create in RW
            _create_in_sde(query_layer, feature_name, SDEADM_RW)

            # Step 4 — create in RO (copy from RW so both are in sync)
            rw_feature = os.path.join(SDEADM_RW, feature_name)
            _create_in_sde(rw_feature, feature_name, SDEADM_RO)

            logger.info(f"Done: {feature_name}")

    except LicenseError as e:
        logger.error(str(e))
        sys.exit(1)

    except arcpy.ExecuteError:
        logger.error(arcpy.GetMessages(2))
        tb = sys.exc_info()[2]
        logger.error("PYTHON ERRORS:\n" + traceback.format_tb(tb)[0] + "\n" + str(sys.exc_info()))
        logger.error("GP ERRORS:\n" + arcpy.GetMessages(2))
        sys.exit(1)

    except Exception as e:
        logger.error(e)
        tb = sys.exc_info()[2]
        logger.error("PYTHON ERRORS:\n" + traceback.format_tb(tb)[0] + "\n" + str(sys.exc_info()))
        logger.error("GP ERRORS:\n" + arcpy.GetMessages(2))
        sys.exit(1)

    finally:
        arcpy.CheckInExtension("LocationReferencing")
        logger.info("Checked in LocationReferencing Extension.")

    end_time = datetime.datetime.now().strftime("%d-%b-%y %H:%M:%S")
    logger.info("-----------------------")
    logger.info(f"End: {end_time}")
