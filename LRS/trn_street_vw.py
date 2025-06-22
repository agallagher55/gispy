import os

import arcpy
import logging
import csv
import sys
import traceback

from os import environ, path
from configparser import ConfigParser
from datetime import datetime

from HRMutils import setupLog, send_mail

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

working_dir = os.path.dirname(sys.path[0])
scripts_dir = os.path.join(working_dir, "Scripts")
scratch_dir = os.path.join(working_dir, "Scratch")
gdb_name = "Scratch.gdb"

scratch_gdb = os.path.join(scratch_dir, gdb_name)

arcpy.CheckOutExtension("LocationReferencing")

config = ConfigParser()
config.read('config.ini')

log_file = path.join(
    os.getcwd(),
    f"{datetime.today().date()}_TRN_street_vw_creation.log"
)
logger = setupLog(log_file)
log_server = ""

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # logger.info logs to console

LRS_DIR = r"\\msfs203.hrm.halifax.ca\GISData\Data Sharing\LRS_operational"
LRS_GDB = os.path.join(LRS_DIR, "lrs_view.gdb")

LRS_VIEW_NAME = "TRNLRS_TRN_street_VW"

PRE_VIEW_FEATURE_NAME = "TRNLRS_segmented_street_events"

class LicenseError(Exception):
    pass


def run_error_processing(error_message):

    logger.info("Handling Error...")

    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]

    pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
            str(sys.exc_info()[0]) + ": " + str(sys.exc_info()[1]) + "\n"

    logger.error(pymsg)
    logger.info(error_message)

    msgs = "GP ERRORS:\n" + arcpy.GetMessages(2) + "\n"
    logger.error(msgs)

    # send_mail(
    #     f"ERROR - GDB Replication Had Failures - Check Log File",
    #     log_server + " / GDB_Replication.py\n" + error_message
    # )


def trnlrs_street_view_checks(dyn_seg_feature: str, short_segment_threshold: float) -> dict:

    import pandas as pd

    duplicate_fdmids_report = f"duplicate_fdmids.txt"
    null_fdmids_report = f"null_fdmids.csv"
    short_segments_report = f"short_segments.csv"

    critical_errors_found = False
    warning_errors_found = False

    dyn_seg_fields = ["ROUTE_ID", "FDMID", "SHAPE@LENGTH"]

    dyn_seg_data = [
        row for row in arcpy.da.SearchCursor(
            dyn_seg_feature,
            dyn_seg_fields, "TO_DATE IS NULL"
        )
    ]

    df = pd.DataFrame(dyn_seg_data, columns=dyn_seg_fields).sort_values(by=["SHAPE@LENGTH", "ROUTE_ID"])
    df['FDMID'] = df['FDMID'].round().astype('Int64')

    # CRITICAL ERROR CHECKS

    # Check for duplicate FDMIDs
    duplicate_fdmids = sorted(df[df.duplicated(subset=['FDMID'], keep=False)]['FDMID'].unique().tolist())

    # Check for null FDMID records
    null_fdmid_df = df[df['FDMID'].isnull()]

    # Check for short segments
    # Filter for short segments
    short_segments_df = df[(df['SHAPE@LENGTH'] < short_segment_threshold) | (df['SHAPE@LENGTH'].isnull())]
    short_segments = short_segments_df.to_dict('records')

    # WARNING CHECKS
    # communities, overlapping ranges, blank street type, NSCAF, locators
    # TODO: Check for warnings

    if duplicate_fdmids:

        critical_errors_found = True

        logger.info("Duplicate FDMIDs found!")

        # Write output txt file
        with open(duplicate_fdmids_report, "w") as txt_file:

            for fdmid in duplicate_fdmids:
                txt_file.write(f"{fdmid}\n")

    if not null_fdmid_df.empty:
        critical_errors_found = True

        logger.info("Records with null FDMIDs found!")

        null_fdmid_records = null_fdmid_df[['ROUTE_ID']].to_dict('records')

        # write route IDs to a text file
        with open(null_fdmids_report, "w", newline='') as csv_file:
            fieldnames = null_fdmid_records[0].keys()  # grab your column order
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()  # write column headers
            writer.writerows(null_fdmid_records)  # write all rows at once

    if short_segments:
        critical_errors_found = True

        # logger.info(f"{len([short_segments.keys()])} Segments shorter than {short_segment_threshold}m found!")
        logger.info(f"Segments shorter than {short_segment_threshold}m found!")

        # write output csv
        with open(short_segments_report, "w", newline='') as csv_file:
            fieldnames = short_segments[0].keys()  # grab your column order
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            writer.writeheader()  # write column headers
            writer.writerows(short_segments)  # write all rows at once

    return {
        "duplicate_fdmids_report": duplicate_fdmids_report,
        "null_fdmids_report": null_fdmids_report,
        "short_segments_report": short_segments_report,

        "critical_errors_found": critical_errors_found,
        "warning_errors_found": warning_errors_found
    }


def update_lrs_dynamic_segmentation(out_db: str, reference_db:str, segmented_feature_name: str = "TRNLRS_segmented_street_events"):
    """
    - Update LRS view by recreating the table that the view is derived from.

    :param segmented_feature_name:
    :return:
    """

    event_tables = [
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetDirection',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetClass',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_AddressRange',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_PSAB',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetOwnership',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetStatus',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_WinterMaintenance',  # NEW
    ]

    network_fields = "OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;GLOBALID"

    if not arcpy.Exists(out_db):
        arcpy.CreateFileGDB_management(
            out_folder_path=os.path.dirname(out_db),
            out_name=os.path.basename(out_db),
        )

    overlay_output_feature = os.path.join(out_db, segmented_feature_name)

    try:

        if arcpy.CheckExtension("LocationReferencing") == "Available":
            arcpy.CheckOutExtension("LocationReferencing")
            logger.info("Checked out LocationReferencing Extension")

        else:
            raise LicenseError

        logger.info(f"Overlaying events to create '{segmented_feature_name}'...")
        arcpy.locref.OverlayEvents(
            in_route_features=rf"{reference_db}\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.LRSN_Route",
            event_layers=event_tables,
            output_dataset=overlay_output_feature,
            include_geometry="INCLUDE_GEOMETRY",
            network_fields=network_fields
        )
        logger.info(arcpy.GetMessages())

        logger.info(f"Recreated {overlay_output_feature}")

        if out_db.upper().endswith(".SDE"):
            arcpy.ChangePrivileges_management(
                in_dataset=overlay_output_feature,
                user="PUBLIC",
                View="GRANT",
            )

        return overlay_output_feature

    except arcpy.ExecuteError:
        run_error_processing(
            f"Error updating Dynamic Segmentation {segmented_feature_name}. Details: {str(arcpy.GetMessages(2))}"
        )

    except LicenseError:
        run_error_processing(
            f"Error updating Dynamic Segmentation {segmented_feature_name}. \n"
            f"Unable to checkout Location Referencing License."
        )

    finally:
        arcpy.CheckInExtension('LocationReferencing')
        logger.info("Checked in LocationReferencing Extension")


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: '{PC_NAME}'\tRunning from: '{run_from}'...")

    output_geodatabase = r"T:\work\giss\monthly\202404apr\gallaga\LRS_TRN_street\New File Geodatabase.gdb"

    arcpy.CheckOutExtension("LocationReferencing")

    VW_DEFINITION = f"SELECT     OBJECTID, SHAPE,  FCODE,  STR_NAME,  STR_TYPE, ROUTENAME,  MUN_CODE, MIX_FULL,  FROM_STR,  TO_STR,  STR_DIR,  STR_STATUS, ST_CLASS,  OWN, DATE_ACCEPT,  COMMENT__2 AS STR_REM, FLAG, PSAB_CODE,  FDMID,  ROUTE_ID,  FROM_LEFT,  TO_LEFT,  FROM_RIGHT,  TO_RIGHT,  OLD_FDMID,  GSA_LEFT,  GSA_RIGHT,  PAR_LEFT,  PAR_RIGHT,  STR_CODE_L,  STR_CODE_R,  ASSETID, LANE, MAINTENANCE FROM {PRE_VIEW_FEATURE_NAME} WHERE to_date IS NULL"

    for dbs in [
        # [
        #     config.get("SERVER", "dev_rw"),
        # ],
        [
            config.get("SERVER", "prod_rw"),
        ],
    ]:

        if dbs:
            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for workspace in dbs:
                logger.info(f"DATABASE: {workspace}")

                with arcpy.EnvManager(workspace=workspace):

                    sde_dyn_seg_feature = os.path.join(workspace, "SDEADM.TRNLRS_segmented_street_events")

                    # Create new dyn seg, not feeding view
                    # pre_dyn_seg_feature = update_lrs_dynamic_segmentation(out_db=LRS_GDB, segmented_feature_name=os.path.basename("TRNLRS_segmented_street_events"))
                    pre_dyn_seg_feature = update_lrs_dynamic_segmentation(
                        out_db=scratch_gdb,
                        reference_db=workspace,
                        segmented_feature_name=os.path.basename("TRNLRS_segmented_street_events")
                    )

                    lrs_email_recipents = ['tr33177@halifax.ca', 'me24191@halifax.ca']
                    short_segment_threshold = 3.174511  # FUNCTION VAR
                    view_checks_info = trnlrs_street_view_checks(pre_dyn_seg_feature, short_segment_threshold)

                    if view_checks_info["critical_errors_found"] or view_checks_info["warning_errors_found"]:

                        reports = view_checks_info['duplicate_fdmids_report'], view_checks_info['null_fdmids_report'], \
                        view_checks_info['short_segments_report'],
                        written_reports = [x for x in reports if os.path.exists(x)]

                        # send_mail(
                        #     to=lrs_email_recipents,
                        #     subject="TRNLRS_street_view Errors & Warnings Report (from PROD)",
                        #     text="Uh oh, we have a small problem, friends - attached is some information regarding some issues feeding the TRNLRS_steet_VW, for your VIEWing pleasure."
                        #          f"\n\t(The shortest segment threshold used was '{short_segment_threshold}')"
                        #          f"\nCheck out geometry information here: '{LRS_GDB}'"
                        #          "\nBreathe, think, review, and keep up the good work."
                        #          "\n\nGodspeed.",
                        #     files=written_reports,
                        #     cc=['gallaga@halifax.ca'],
                        # )

                    else:
                        # Truncate and load
                        logger.info(f"Truncating {sde_dyn_seg_feature}...")
                        arcpy.TruncateTable_management(sde_dyn_seg_feature)

                        logger.info(f"Loading {sde_dyn_seg_feature}...")
                        arcpy.Append_management(
                            inputs=pre_dyn_seg_feature,
                            target=sde_dyn_seg_feature,
                            schema_type="NO_TEST",
                        )

    # arcpy.CheckInExtension('LocationReferencing')
