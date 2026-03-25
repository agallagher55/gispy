"""
update_sde_metadata.py

Reads a Spatial Data Submission Form (SDSF) Excel file and updates the SDE
metadata for the corresponding feature class.

Fields updated from SDSF:
    - Title          (Dataset Name)
    - Description    (Dataset Description)
    - Summary        (Dataset Purpose)
    - Tags           (Dataset Tags)
    - Access Constraints (Notes or Disclaimers)
    - Revised Date   (today's date)

Usage:
    1. Set SDSF_PATH to the path of the SDSF Excel file.
    2. Set FEATURE to the SDE feature name (e.g. "SDEADM.LND_ANS_communities").
       Leave blank to derive the name from the SDSF "Dataset Name" field.
    3. Uncomment the database tiers (dev / qa / prod) you want to update.
    4. Run the script.
"""

import os
import sys
import traceback
import datetime

from configparser import ConfigParser

import arcpy

from metadata import SDSFMetaData, get_sde_metadata, update_metadata

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

# ── User configuration ─────────────────────────────────────────────────────────

# Path to the SDSF Excel workbook
SDSF_PATH = r"T:\work\giss\monthly\202603mar\gallaga\LND_PPLC_xxx_applications\Create new feature class LND_PPLC_ planning_applications.xlsx"  # TODO: Update me

# SDE feature to update, e.g. "SDEADM.LND_ANS_communities"
# Leave empty ("") to use the Dataset Name from the SDSF.
FEATURE = ""

# ── Logging ────────────────────────────────────────────────────────────────────

import logging

log_file = os.path.join(os.getcwd(), f"{datetime.date.today()}_update_sde_metadata.log")
logger = logging.getLogger("update_sde_metadata")
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

log_formatter = logging.Formatter(
    "%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
)
file_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# ── Config ─────────────────────────────────────────────────────────────────────

config = ConfigParser()
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
config.read(os.path.join("config.ini"))

run_from = "SERVER" if "APP" in os.environ.get("COMPUTERNAME", "").upper() else "LOCAL"

if __name__ == "__main__":

    logger.info("=" * 60)
    logger.info(f"SDSF: {SDSF_PATH}")

    # ── Read SDSF metadata ─────────────────────────────────────────────────────
    try:

        sdsf = SDSFMetaData(SDSF_PATH)

    except Exception as e:

        logger.error(f"Failed to read SDSF: {e}")
        sys.exit(1)

    # Strip the "METADATA: " prefix that SDSFMetaData prepends to the name
    dataset_name = sdsf.name.replace("METADATA: ", "").strip()

    feature = FEATURE if FEATURE else dataset_name

    logger.info(f"Feature: {feature}")
    logger.info(f"Dataset name from SDSF : {dataset_name}")
    logger.info(f"Description            : {str(sdsf.description)[:80]}...")
    logger.info(f"Summary                : {str(sdsf.summary)[:80]}...")
    logger.info(f"Tags                   : {sdsf.tags}")
    logger.info(f"Limitations            : {str(sdsf.limitations)[:80]}...")

    # Build update options from SDSF
    today = datetime.datetime.today().strftime("%Y-%m-%dT00:00:00")

    update_options = {
        "title": dataset_name,
        "description": str(sdsf.description) if sdsf.description else None,
        "summary": str(sdsf.summary) if sdsf.summary else None,
        "tags": str(sdsf.tags) if sdsf.tags else None,
        "access_constraints": str(sdsf.limitations) if sdsf.limitations else None,
        "revised_date": today,
    }

    # ── Database loop ──────────────────────────────────────────────────────────
    for dbs in [

        [config.get(run_from, "dev_rw")],
        # [config.get(run_from, "qa_rw")],
        # [config.get(run_from, "prod_rw")],

    ]:

        if dbs:

            for db in dbs:

                logger.info(f"\nDatabase: {db}")

                with arcpy.EnvManager(workspace=db):

                    # Strip schema prefix for GDB connections
                    fc = (
                        feature.split(".")[-1]
                        if db.lower().endswith(".gdb")
                        else feature
                    )

                    logger.info(f"Reading current metadata for {fc}...")

                    try:

                        current_meta = get_sde_metadata(db, fc)
                        logger.info(f"  Current title   : {current_meta.get('TITLE')}")
                        logger.info(f"  Current rev date: {current_meta.get('REVISION_DATE')}")

                        logger.info(f"Updating metadata for {fc}...")
                        update_metadata(db, fc, update_options)
                        logger.info("Metadata update complete.")

                    except arcpy.ExecuteError:

                        logger.error(arcpy.GetMessages(2))

                    except Exception as e:

                        logger.error(e)
                        tb = sys.exc_info()[2]
                        tbinfo = traceback.format_tb(tb)[0]
                        logger.error("PYTHON ERRORS:\n" + tbinfo + "\n" + str(sys.exc_info()))
                        logger.error("GP ERRORS:\n" + arcpy.GetMessages(2))
                        sys.exit()

    logger.info("Done.")
