import arcpy
import logging
import os
import datetime

from configparser import ConfigParser
from os import environ

from HRMutils import setupLog

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

logFile = os.path.join(os.getcwd(), f"{datetime.date.today()}_loggies.log")
logger = setupLog(logFile)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # print logs to console

if __name__ == "__main__":

    # TODO: UPDATE ME
    FEATURE = "SDEADM.TRN_street_non_hrm"

    FIELD_DEFAULTS = {
        "FCODE": "RRRD",
        "STR_STATUS": "OPEN",
        "FROM_ELEV": 0,
        "TO_ELEV": 0,
        "STR_REM": "STREET LOCATED OUTSIDE OF HRM",
        "PSAB_CODE": "DM",
        "ACC": "NSPRD",
        "SOURCE": "DM",
        "FROM_LEFT": 0,
        "TO_LEFT": 0,
        "FROM_RIGHT": 0,
        "TO_RIGHT": 0,
        "PAR_LEFT": "OR",
        "PAR_RIGHT": "EL",
    }

    REMOVE_DEFAULTS = {
        # "TWSI_MAT",
    }

    SUBTYPE_CODES = [
        # '1: Natural Area Descriptions',
    ]

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    for dbs in [

        [
            config.get(run_from, "dev_rw"),
        ],

        # [
        #     config.get(run_from, "qa_rw"),
        # ],

        # [
        #     config.get(run_from, "prod_rw"),
        # ],
    ]:

        logger.info("=" * 100)

        if dbs:

            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for db in dbs:

                logger.info("-" * 100)
                logger.info(f"Processing workspace: '{db}'...")

                with arcpy.EnvManager(workspace=db):

                    try:

                        if ".GDB" in db.upper():
                            FEATURE = FEATURE.split(".")[-1]

                        # Get subtypes
                        subtypes = arcpy.da.ListSubtypes(FEATURE)
                        subtype_codes = [f'{s}: {subtypes[s]["Name"]}' for s in subtypes]

                        if FIELD_DEFAULTS:

                            for field_name, field_default in FIELD_DEFAULTS.items():


                                    logger.info(f"Setting {field_name} default to '{field_default}'...")

                                    result = arcpy.AssignDefaultToField_management(
                                        in_table=FEATURE,
                                        field_name=field_name,
                                        default_value=field_default,
                                        subtype_code=SUBTYPE_CODES,
                                        clear_value="DO_NOT_CLEAR"
                                    )[0]

                                    logger.info(arcpy.GetMessages(0))

                        if REMOVE_DEFAULTS:

                            for field_name in REMOVE_DEFAULTS:

                                logger.info(f"Removing {field_name} default...")

                                result = arcpy.AssignDefaultToField_management(
                                    in_table=FEATURE,
                                    field_name=field_name,
                                    subtype_code=SUBTYPE_CODES,
                                    clear_value="CLEAR_VALUE"
                                )[0]

                                logger.info(arcpy.GetMessages(0))

                    except Exception as e:
                        logger.error(e)
