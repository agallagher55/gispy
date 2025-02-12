import arcpy

from gispy import (
    utils,
    domains
)

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
    "ADM_poll_location_status": {
        "description": "",
        "field_type": "TEXT",
        "domain_type": "CODED",
        "values": {
            'NOAVAIL': 'Cannot Use/Not Available',
            'NOSTART': 'Not Started',
            'ESCALATE': 'Requires Team Lead Escalation',
            'NOCONT': 'Initial - Attempting Contact – Wrong Contact Information',
            'EMAIL': 'Initial - Awaiting response - Initial Contact made by Email',
            'VOICEMAIL': 'Initial - Awaiting response - Initial Contact made by leaving Voicemail',
            'CORRESP': 'In Progress - In Correspondence with Contact',
            'CONFIRM': 'In Progress - Verbal Confirmation',
            'START': 'In Progress - Accessibility Assessment Started',
            'COMPL': 'In Progress - Accessibility Assessment Complete',
            'FAILED': 'In Progress - Accessibility Assessment Failed',
            'AWAITSIG': 'ooked - Awaiting Contract signature',
            'AWAITINV': 'Booked - Awaiting Invoice',
            'INVOICED': 'Booked – Contract signed and Invoiced',
            'BOOKED': 'Booked - No invoice required',
        }
    },
}

if __name__ == "__main__":
    local_gdb = utils.create_fgdb(CURRENT_DIR)

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    # TODO: Add to WEBGIS? web_ro?

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
