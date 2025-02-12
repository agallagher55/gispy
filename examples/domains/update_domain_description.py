"""
Test updating the description of a domain
"""

import arcpy

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

DOMAIN_UPDATE_PROPERTIES = {
    "AST_bikefeature_type": {
        "description": "Identifies the type of bike feature"
    },
    "AST_bikefeature_finish": {
        "description": "Identifies the finish of the bike feature"
    },
    "AST_bikefeature_make": {
        "description": "Identifies the manufacturer of the bike feature"
    },
}

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    print(f"\nPC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    for dbs in [
        # [local_gdb, ],
        # [
        #     config.get("SERVER", "dev_rw"),
        #     config.get("SERVER", "dev_ro"),
        #     config.get("SERVER", "dev_web_ro_gdb"),
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
            print(f"\nProcessing dbs: {', '.join(dbs)}...")

            for db in dbs:
                print(f"\nDATABASE: {db}")

                db_domains = {x.name: x for x in arcpy.da.ListDomains(db)}

                for domain in DOMAIN_UPDATE_PROPERTIES:
                    # TODO: get target domains (ADD_CODE_VALUES)

                    print(f"\tDomain: {domain}")
                    domain_obj = db_domains.get(domain)

                    if domain_obj:

                        # update domain description
                        update_desc = DOMAIN_UPDATE_PROPERTIES[domain].get("description")
                        print(f"\tUpdate Description: {update_desc}")
                        arcpy.AlterDomain_management(
                            in_workspace=db,
                            domain_name=domain,
                            new_domain_description=update_desc,
                        )
                        print(arcpy.GetMessages())

                    else:
                        print()

