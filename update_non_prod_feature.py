import os

import arcpy
import logging

from os import environ, path
from configparser import ConfigParser
from datetime import datetime

from hrmutils.HRMutils import setupLog

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

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

CIVIC_FEATURE_NAME = "SDEADM.LND_civic_address"

PROD_SDE_RW = config.get("SERVER", "prod_rw")


def update_non_prod_feature(feature, prod_workspace, in_replica=True):

    print(f"Updating {feature} from non-prod environment...")

    feature_name = os.path.basename(feature)
    prod_feature = os.path.join(prod_workspace, feature_name)

    workspace = arcpy.env.workspace
    non_prod_feature = os.path.join(workspace, feature)

    if not workspace:
        raise ValueError("Input feature has no identified workspace...")

    # Update RW
    with arcpy.EnvManager(preserveGlobalIds=True, workspace=workspace):

        print("Truncating feature...")

        # Truncate table - only if non-versioned
        arcpy.DeleteRows_management(in_rows=feature)
        print(arcpy.GetMessages())

        # Append
        print("Updating feature...")
        arcpy.Append_management(
            inputs=prod_feature,
            target=feature,
            schema_type="NO_TEST",
        )
        print(arcpy.GetMessages())

    # Update RO if feature is not in a replica, else, sync replica
    if in_replica:
        print("*SYNC RELATED REPLICA!")


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: '{PC_NAME}'\tRunning from: '{run_from}'...")

    for dbs in [
        # [local_gdb, ],

        # [
        #     config.get("SERVER", "dev_rw"),
        # ],

        [
            config.get("SERVER", "qa_rw"),
            # config.get("SERVER", "qa_ro"),
            # config.get("SERVER", "qa_web_ro_gdb"),
            # config.get("SERVER", "qa_web_ro"),
        ],

        # [
        #     # config.get("SERVER", "prod_rw"),
        #     # config.get("SERVER", "prod_ro"),
        #     # config.get("SERVER", "prod_web_ro_gdb"),
        #     config.get("SERVER", "prod_ro_web"),
        # ],

    ]:

        if dbs:
            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for workspace in dbs:
                logger.info(f"DATABASE: {workspace}")

                with arcpy.EnvManager(workspace=workspace):

                    update_non_prod_feature(CIVIC_FEATURE_NAME, PROD_SDE_RW)


