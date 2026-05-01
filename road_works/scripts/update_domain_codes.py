import arcpy
import logging
import datetime
import os

from gispy import (
    domains,
    utils
)

from hrmutils.HRMutils import setupLog

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

logFile = os.path.join(os.getcwd(), f"{datetime.date.today()}_field_type.log")
logger = setupLog(logFile)
logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # print logs to console


CURRENT_DIR = getcwd()

ADD_CODE_VALUES = {

    "TRN_RDM_EncroachEditors": {
        'Kayode Taiwo': "Kayode Taiwo",
    },


}

REMOVE_CODE_VALUES = {
    # "AST_tree_condition": [4, ],
}

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    local_gdb = utils.create_fgdb(out_folder_path=CURRENT_DIR, out_name="scratch.gdb")

    for dbs in [
        # [local_gdb, ],

        # [
            # config.get("SERVER", "dev_rw"),
            # config.get("SERVER", "dev_ro"),
            # config.get("SERVER", "dev_web_ro_gdb"),
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
            logger.info("=" * 100)

            if dbs:
                logger.info(f"Processing dbs: {', '.join(dbs)}...")

                for db in dbs:
                    logger.info("-" * 100)
                    logger.info(f"DATABASE: {db}")

                    if db == local_gdb:

                        # Check for domains in local workspace
                        required_domains = set(list(ADD_CODE_VALUES.keys()) + list(REMOVE_CODE_VALUES.keys()))
                        domain_present, unfound_domains = domains.domains_in_db(local_gdb, required_domains)

                        if unfound_domains:
                            prod_sde = config.get("SERVER", "prod_rw") if "APP" in PC_NAME else config.get("LOCAL",
                                                                                                           "prod_rw")

                            domains.transfer_domains(
                                unfound_domains,
                                local_gdb,
                                from_workspace=prod_sde
                            )

                    for domain in REMOVE_CODE_VALUES:

                        remove_codes = REMOVE_CODE_VALUES[domain]

                        for count, domain_code in enumerate(remove_codes, start=1):
                            domains.remove_code_value(db, domain, domain_code)

                    for domain in ADD_CODE_VALUES:
                        logger.info(f"DOMAIN: {domain}")

                        # Check that domain is found in database connection
                        domain_found, unfound_domains = domains.domains_in_db(db, [domain])

                        if not domain_found:
                            raise ValueError(
                                f"Did not find domain '{domain}' in db. Unfound domains: {', '.join(unfound_domains)}")

                        add_code_values = ADD_CODE_VALUES[domain]
                        for count, code_value in enumerate(add_code_values, start=1):
                            new_value = add_code_values[code_value]

                            logger.info(f"{count}/{len(add_code_values)}) Domain and Code: {code_value} & {new_value}")
                            domains.add_code_value(db, domain, code_value, new_value)

                        logger.info(f"Sorting domain...")
                        arcpy.SortCodedValueDomain_management(
                            in_workspace=db,
                            domain_name=domain,
                            sort_by="DESCRIPTION",
                            sort_order="ASCENDING"
                        )
