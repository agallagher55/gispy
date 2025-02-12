from configparser import ConfigParser
from datetime import date
from os import (
    environ, getcwd, path
)

import arcpy
import logging

from gispy import utils
from gispy.features import Feature

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

log_file = path.join(
    getcwd(),
    f"{date.today()}_add_fields.log"
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

CURRENT_DIR = getcwd()

UPDATE_FEATURE = "SDEADM.TRN_pavement_marking"  # TODO: UPDATE ME

SPATIAL_REFERENCE = None

# TODO: UPDATE ME
delete_fields = [
    'BWL_1_8_QTY',
    'BWL_0_5_QTY',
    'BWL_3_0_QTY',
]

if __name__ == "__main__":
    local_gdb = utils.create_fgdb(CURRENT_DIR)

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    for dbs in [
        # [local_gdb, ],

        # WEBGIS features can use domains from SDEADM owner - don't need to create a domain for both SDEADM and WEBGIS

        [
            config.get(run_from, "dev_rw"),
            # config.get(run_from, "dev_ro"),
            # config.get(run_from, "dev_web_ro_gdb")
        ],

        # [
            # config.get(run_from, "qa_rw"),
            # config.get(run_from, "qa_ro"),
            # config.get(run_from, "qa_web_ro_gdb")
        # ],
        # [
        #     config.get(run_from, "prod_rw"),
        #     config.get(run_from, "prod_ro"),
        #     config.get(run_from, "prod_web_ro_gdb")
        # ],
    ]:

        if dbs:
            logger.info(f"\nProcessing dbs: {', '.join(dbs)}...")

            for db in dbs:
                logger.info(f"DATABASE: {db}")

                if db.endswith(".gdb"):
                    UPDATE_FEATURE = UPDATE_FEATURE.replace("SDEADM.", "")

                elif "WEBGIS" in db.upper():
                    UPDATE_FEATURE = UPDATE_FEATURE.replace("SDEADM.", "WEBGIS.")

                logger.info(f"Feature: {UPDATE_FEATURE}")

                with arcpy.EnvManager(workspace=db):

                    # Check if feature exists
                    if not arcpy.Exists(UPDATE_FEATURE):
                        raise ValueError(f"\tFeature, '{UPDATE_FEATURE}', does not exist.")

                    desc = arcpy.Describe(UPDATE_FEATURE)

                    arcpy.DeleteField_management(
                        in_table=UPDATE_FEATURE,
                        drop_field=delete_fields,
                        method="DELETE_FIELDS"
                    )
                    logger.info(arcpy.GetMessages())

                    # TODO: Start services
                    # * Had to manually unlock with SDE connection
