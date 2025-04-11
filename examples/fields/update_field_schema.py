"""
Date:
"""

import arcpy
import os
import sys
import datetime
import time
import traceback
import logging

from configparser import ConfigParser

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

log_file = os.path.join(
    os.getcwd(),
    f"{datetime.date.today()}_alter_fields.log"
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
# VARIABLES
update_feature_info = {
    "SDEADM.TRN_curb_use": {
        "field": "COMMENTS",
        "new_length": 100,
    },
    # "SDEADM.CEN_census_subdivision_2016": {
    #     "field": "LANDAREA",
    #     "new_alias": "Land Area (sq km)",
    # },
}


# Functions
def update_field_config(feature, field=None, alias=None, name=None, field_type=None, length=None, nullable=None):

    logger.info(f"Updating field configuration...")

    arcpy.AlterField_management(
        in_table=feature,
        field=field,
        new_field_name=name,
        new_field_alias=alias,
        field_type=field_type,
        field_length=length,
        field_is_nullable=nullable,
        clear_field_alias='#'
    )
    logger.info(arcpy.GetMessages())


if __name__ == "__main__":

    startTime = time.asctime(time.localtime(time.time()))
    logger.info("Start: " + startTime)
    logger.info("-----------------------")

    PC_NAME = os.environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"\nPC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    try:

        for dbs in [
            # [
                # config.get(run_from, "dev_rw"),
                # config.get(run_from, "dev_ro"),
                # config.get(run_from, "dev_web_ro_gdb")
            # ],
            # [
            #     config.get("SERVER", "qa_rw"),
            #     config.get("SERVER", "qa_ro"),
            #     config.get("SERVER", "qa_web_ro_gdb"),
            # ],
            [
                config.get("SERVER", "prod_rw"),
                config.get("SERVER", "prod_ro"),
                config.get("SERVER", "prod_web_ro_gdb"),
            ],
        ]:
            if dbs:
                logger.info(f"\nProcessing dbs: {', '.join(dbs)}...")

                for db in dbs:
                    logger.info(f"\nDATABASE: {db}")

                    for update_feature in update_feature_info:

                        if db.upper().endswith("GDB"):
                            update_feature = update_feature.upper().replace("SDEADM.", "")

                        with arcpy.EnvManager(workspace=db):

                            field = update_feature_info[update_feature]['field']

                            new_alias = update_feature_info[update_feature].get('new_alias')
                            new_length = update_feature_info[update_feature].get('new_length')
                            new_name = update_feature_info[update_feature].get('new_name')
                            new_type = update_feature_info[update_feature].get('new_type')

                            update_field_config(
                                feature=update_feature,
                                field=field,
                                name=new_name,
                                alias=new_alias,
                                field_type=new_type,
                                length=new_length,
                                nullable="#",
                            )

                            logger.info(arcpy.GetMessages())

    except arcpy.ExecuteError:
        arcpy_msg = arcpy.GetMessages(2)
        logger.error(arcpy_msg)

    except Exception as e:
        logger.info(e)

        # Return any python specific errors as well as any errors from the geoprocessor
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]
        pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
                str(sys.exc_info()[0]) + ": " + str(sys.exc_info()[1]) + "\n"
        logger.error(pymsg)

        msgs = "GP ERRORS:\n" + arcpy.GetMessages(2) + "\n"
        logger.error(msgs)

        # send_error("ERROR - BUILDING PERMIT ERROR", "DC1-GIS-APP-Q203 / BuildingPermits.py")

        sys.exit()

    # Close the Log File:
    endTime = time.asctime(time.localtime(time.time()))
    logger.info("-----------------------")
    logger.info("End: " + endTime)
