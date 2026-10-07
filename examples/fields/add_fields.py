from configparser import ConfigParser
from datetime import date

from os import (
    environ, getcwd, path
)

import arcpy
import logging

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

# TODO: UPDATE ME
new_field_info = {
    "SDEADM.SER_DRY_HYDRANT": {
        "ASSETSTAT": {
            "alias": "Asset Status",
            "field_type": "TEXT",
            "field_length": "5",
            "nullable": "NULLABLE",
            "default": "",
            "domain": "AAA_asset_stat"
        },

    },
}

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    # Disconnect SDE sessions (e.g. map services) holding a schema lock on the feature before adding fields
    UNLOCK = True

    for dbs in [
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
            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for db in dbs:
                logger.info(f"DATABASE: {db}")

                for feature_key in new_field_info:

                    update_feature = feature_key.replace("SDEADM.", "") if db.endswith(".gdb") else feature_key

                    logger.info(f"Feature: {update_feature}")

                    with arcpy.EnvManager(workspace=db):

                        # Check if feature exists
                        if not arcpy.Exists(update_feature):
                            if db.endswith(".gdb"):
                                logger.warning(f"\tFeature, '{update_feature}', does not exist in {db}. Skipping...")
                                continue
                            raise ValueError(f"\tFeature, '{update_feature}', does not exist.")

                        desc = arcpy.Describe(update_feature)

                        my_feature = Feature(db, desc.baseName, "POINT")
                        current_fields = [x.name for x in arcpy.ListFields(update_feature)]

                        # TODO: Stop services

                        update_feature_new_field_info = new_field_info[feature_key]

                        for field in update_feature_new_field_info:
                            logger.info(f"Field to add: '{field}'")

                            # Check that field doesn't already exist

                            if field in current_fields:
                                logger.info(f"Field, {field} already exists in {update_feature}..!")
                                continue

                            logger.info(f"Adding {field} to {update_feature}...")
                            my_feature.add_field(
                                field_name=field,
                                field_type=update_feature_new_field_info[field]["field_type"],
                                length=update_feature_new_field_info[field].get("field_length", "#"),
                                alias=update_feature_new_field_info[field]["alias"],
                                domain_name=update_feature_new_field_info[field]["domain"],
                                unlock=UNLOCK
                            )

                        # TODO: Start services
                        # * Had to manually unlock with SDE connection
