import os

import arcpy
import logging

from os import environ, path
from configparser import ConfigParser
from datetime import datetime

from hrmutils.HRMutils import setupLog

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

arcpy.CheckOutExtension("LocationReferencing")

config = ConfigParser()
config.read('config.ini')

logFile = path.join(
    os.getcwd(),
    f"{datetime.today().date()}_TRN_street_vw_creation.log"
)
logger = setupLog(logFile)

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # logger.info logs to console

LRS_VIEW_NAME = "TRNLRS_TRN_street_VW"

PRE_VIEW_FEATURE_NAME = "TRNLRS_segmented_street_events"


def update_lrs_view(event_tables: [list, tuple], segmented_feature_name: str, network_fields, view_name: str):
    """
    - Update LRS view by recreating the table that the view is derived from.

    :param event_tables: event tables used for the view (and overlay events process)
    :param segmented_feature_name:
    :param network_fields:
    :param view_name:
    :return:
    """

    logger.info(f"Updating LRS view '{view_name}'...")

    overlay_output_feature = path.join(workspace, segmented_feature_name)

    logger.info(f"Overlaying events to create '{segmented_feature_name}'...")
    arcpy.locref.OverlayEvents(
        in_route_features=rf"{workspace}\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.LRSN_Route",
        event_layers=event_tables,
        output_dataset=overlay_output_feature,
        include_geometry="INCLUDE_GEOMETRY",
        network_fields=network_fields
    )
    logger.info(arcpy.GetMessages())

    return overlay_output_feature


def create_lrs_view(
        event_tables: [list, tuple], segmented_feature_name: str, view_name: str, sql_definition: str,
        workspace: str, network_fields
):
    logger.info(f"Creating LRS view '{view_name}'...")

    output_view_feature = path.join(workspace, view_name)

    overlay_output_feature = update_lrs_view(event_tables, segmented_feature_name, network_fields, view_name)

    logger.info(f"Creating database view '{view_name}'...")
    arcpy.CreateDatabaseView_management(
        input_database=workspace,
        view_name=view_name,
        view_definition=sql_definition
    )

    # Update privileges
    for feature in (
            overlay_output_feature,
            output_view_feature,
    ):
        logger.info(f"Updating privileges on {feature}...")
        arcpy.ChangePrivileges_management(
            in_dataset=feature,
            user="PUBLIC",
            View="GRANT",
        )

    logger.warning("*MUST SET VIEW PROJECTION IN ARC CATALOG!!")

    return output_view_feature


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: '{PC_NAME}'\tRunning from: '{run_from}'...")

    output_geodatabase = r"T:\work\giss\monthly\202404apr\gallaga\LRS_TRN_street\New File Geodatabase.gdb"

    arcpy.CheckOutExtension("LocationReferencing")

    VW_DEFINITION = f"SELECT     OBJECTID, SHAPE,  FCODE,  STR_NAME,  STR_TYPE, ROUTENAME,  MUN_CODE, MIX_FULL,  FROM_STR,  TO_STR,  STR_DIR,  STR_STATUS, ST_CLASS,  OWN, DATE_ACCEPT,  COMMENT__2 AS STR_REM, FLAG, PSAB_CODE,  FDMID,  ROUTE_ID,  FROM_LEFT,  TO_LEFT,  FROM_RIGHT,  TO_RIGHT,  OLD_FDMID,  GSA_LEFT,  GSA_RIGHT,  PAR_LEFT,  PAR_RIGHT,  STR_CODE_L,  STR_CODE_R,  ASSETID, LANE, MAINTENANCE FROM {PRE_VIEW_FEATURE_NAME} WHERE to_date IS NULL"

    for dbs in [
        # [local_gdb, ],

        # [
        #     config.get("SERVER", "dev_rw"),
        # ],

        # [
        #     config.get("SERVER", "qa_rw"),
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
                    # Overlay events
                    trn_street_event_layers = [
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_StreetDirection',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_StreetClass',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_AddressRange',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_PSAB',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_StreetOwnership',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_StreetStatus',
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_Lane',  # NEW
                        rf'{workspace}\SDEADM.TRNLRS\SDEADM.E_WinterMaintenance',  # NEW
                    ]

                    create_lrs_view(
                        event_tables=trn_street_event_layers,
                        segmented_feature_name=PRE_VIEW_FEATURE_NAME,
                        view_name=LRS_VIEW_NAME,
                        sql_definition=VW_DEFINITION,
                        workspace=workspace,
                        network_fields="OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;MIX_FULL;GLOBALID"
                    )

                    update_lrs_view(
                        event_tables=trn_street_event_layers,
                        segmented_feature_name=PRE_VIEW_FEATURE_NAME,
                        network_fields="OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;MIX_FULL;GLOBALID",
                        view_name=LRS_VIEW_NAME
                    )

                    logger.info("SET VIEW PROJECTION IN ARC CATALOG")
                    # Set projection with Catalog
                    # In RO check TRN_street_alias

    # arcpy.CheckInExtension('LocationReferencing')
