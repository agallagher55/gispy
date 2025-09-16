import arcpy

import domains

from configparser import ConfigParser
from os import (
    getcwd,
    environ
)

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

NEW_DOMAINS = {
    "LND_indigenous_land_classification": {
        "description": "",
        "field_type": "TEXT",
        "domain_type": "CODED",
        "values": {
            "LEG": "Legislated Land",
            "TRT": "Treaty/Settlement Land",
            "SGA": "Self-Governed Land",
            "IOL": "Indigenous-Owned Land",
            "TRD": "Traditional Use Area",
            "REL": "Reserve Land",
            "INT": "Interim Recognition",
            "UNK": "Unknown",
        }
    },
}

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    for dbs in [
        # [local_gdb, ],

        # WEBGIS features can use domains from SDEADM owner - don't need to create a domain for both SDEADM and WEBGIS

        [
            config.get(run_from, "dev_rw"),
            config.get(run_from, "dev_ro"),
            config.get(run_from, "dev_web_ro_gdb")
        ],

        # [
        #     config.get(run_from, "qa_rw"),
        #     config.get(run_from, "qa_ro"),
        #     # config.get(run_from, "qa_web_ro_gdb")
        # ],
        # [
        #     config.get(run_from, "prod_rw"),
        #     config.get(run_from, "prod_ro"),
        # #     config.get(run_from, "prod_web_ro_gdb")
        # ],
    ]:

        if dbs:
            print(f"\nProcessing dbs: {', '.join(dbs)}...")

            for db in dbs:
                print(f"\nDATABASE: {db}")

                with arcpy.EnvManager(workspace=db):

                    for domain in NEW_DOMAINS:

                        domains.create_domain(
                            workspace=db,
                            domain_name=domain,
                            domain_description=NEW_DOMAINS[domain]["description"],
                            field_type=NEW_DOMAINS[domain]["field_type"],
                            domain_type=NEW_DOMAINS[domain]["domain_type"],
                        )

                        add_code_values = NEW_DOMAINS[domain]['values']

                        for count, code_value in enumerate(add_code_values, start=1):
                            new_value = add_code_values[code_value]

                            print(f"\n{count}/{len(add_code_values)}) Domain and Code: {code_value} & {new_value}")
                            domains.add_code_value(db, domain, code_value, new_value)
