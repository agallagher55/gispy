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

    DOMAIN_FIELD_INFO = {

        "SDEADM.LND_outdoor_rec_equip_point": {
            "CLASS": "LND_rec_space_class",
        },

        "SDEADM.LND_outdoor_rec_poly": {
            "CLASS": "LND_rec_space_class",
        },

        "SDEADM.LND_outdoor_rec_use": {
            "BDCLASS": "LND_rec_space_class",
            "SUBTYPES": ['1', '7']
            # "BDCLASS": "LND_rec_space_class",  # + Subtype
            # "BDCLASS": "LND_rec_space_class",  # + Subtype
        },
    }

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    for dbs in [

        # [
        #     config.get(run_from, "dev_rw"),
        #     config.get(run_from, "dev_ro"),
        # ],

        [
            # config.get("SERVER", "qa_rw"),
            # config.get("SERVER", "qa_ro"),
            config.get("SERVER", "qa_web_ro_gdb"),
        ],
        [
            # config.get("SERVER", "prod_rw"),
            # config.get("SERVER", "prod_ro"),
            config.get("SERVER", "prod_web_ro_gdb"),
        ],
    ]:

        logger.info("=" * 100)

        if dbs:

            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for db in dbs:

                logger.info("-" * 100)
                logger.info(f"Processing workspace: '{db}'...")

                with arcpy.EnvManager(workspace=db):

                    try:

                        for feature in DOMAIN_FIELD_INFO:

                            logger.info(feature)

                            logger.info("-" * 100)

                            field_domains = [x for x in DOMAIN_FIELD_INFO[feature] if x != "SUBTYPES"]

                            for field in field_domains:

                                domain = DOMAIN_FIELD_INFO[feature][field]
                                subtypes = DOMAIN_FIELD_INFO[feature].get("SUBTYPES", [])

                                logger.info(f"{field}: {domain}")

                                if ".GDB" in db.upper():
                                    feature = feature.split(".")[-1]

                                if not subtypes:
                                    arcpy.AssignDomainToField_management(
                                        in_table=feature,
                                        field_name=field,
                                        domain_name=domain,
                                        subtype_code=None
                                    )

                                else:

                                    for subtype in subtypes:

                                        print(f"Subtype: {subtype}")

                                        arcpy.AssignDomainToField_management(
                                            in_table=feature,
                                            field_name=field,
                                            domain_name=domain,
                                            subtype_code=subtype
                                        )
                                logger.info(arcpy.GetMessages())

                    except Exception as e:
                        logger.error(e)
