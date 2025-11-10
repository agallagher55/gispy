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

from zipp.glob import separate

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
    "SDEADM.TRN_traffic_calming_assessm": [
        {
            "field": "FILE_NAME",
            # "new_name": "DESIG",
            "new_alias": "Original Speed File",
        },
        {
            "field": "UFILE_NAME",
            "new_alias": "Updated Speed File",
        },
    ]
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

    separator = "-" * 70

    start_time = time.asctime(time.localtime(time.time()))
    logger.info(f"Start: {start_time}")
    logger.info(separator)

    PC_NAME = os.environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: {PC_NAME}Running from: {run_from}...")

    try:

        for dbs in [
            [
            config.get(run_from, "dev_rw"),
            # config.get(run_from, "dev_ro"),
            # config.get(run_from, "dev_web_ro_gdb")
            ],
            # [
            #     config.get("SERVER", "qa_rw"),
            #     config.get("SERVER", "qa_ro"),
            #     config.get("SERVER", "qa_web_ro_gdb"),
            # ],
            # [
            #     config.get("SERVER", "prod_rw"),
            #     config.get("SERVER", "prod_ro"),
            #     config.get("SERVER", "prod_web_ro_gdb"),
            # ],
        ]:
    
            if dbs:
                logger.info(f"Processing dbs: {', '.join(dbs)}...")
    
                for db in dbs:
                    logger.info(f"DATABASE: {db}")
    
                    for update_feature in update_feature_info:
    
                        with arcpy.EnvManager(workspace=db):
    
                            for field_info in update_feature_info[update_feature]:
    
                                field = field_info['field']
    
                                new_alias = field_info.get('new_alias')
                                new_length = field_info.get('new_length')
                                new_name = field_info.get('new_name')
                                new_type = field_info.get('new_type')
    
                                if db.upper().endswith("GDB"):
                                    update_feature = update_feature.upper().replace("SDEADM.", "")
    
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

        sys.exit()

    # Close the Log File:
    end_time = time.asctime(time.localtime(time.time()))
    logger.info(separator)
    logger.info(f"End: {end_time}")
