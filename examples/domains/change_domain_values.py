import arcpy

import domains

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

ADD_CODE_VALUES = {
    "LND_zoning_DART": {
        "US-E": "US-E",
    },
    "LND_zoning_SHUB": {
        "US-E": "US-E",
    },
}

REMOVE_CODE_VALUES = {
    # "Bldg_fsa_code": ["MOU", "OFM",],
}

if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    print(f"\nPC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    for dbs in [
        # [local_gdb, ],
        # [
            # config.get("SERVER", "dev_rw"),
            # config.get("SERVER", "dev_ro"),
            # config.get("SERVER", "dev_web_ro_gdb"),  # ValueError: Did not find domain 'Bldg_fsa_code' in db. Found domains: Bldg_fsa_code
        # ],
        [
            config.get("SERVER", "qa_rw"),
            config.get("SERVER", "qa_ro"),
            config.get("SERVER", "qa_web_ro_gdb"),
        ],
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

                for domain in REMOVE_CODE_VALUES:

                    remove_codes = REMOVE_CODE_VALUES[domain]

                    for count, domain_code in enumerate(remove_codes, start=1):
                        domains.remove_code_value(db, domain, domain_code)

                for domain in ADD_CODE_VALUES:
                    print(f"\tDOMAIN: {domain}")

                    # Check that domain is found in database connection
                    domain_found, unfound_domains, db_domains = domains.domains_in_db(db, [domain])

                    if not domain_found:
                        raise ValueError(
                            f"Did not find domain '{domain}' in db. Unfound domains: {', '.join(unfound_domains)}")

                    add_code_values = ADD_CODE_VALUES[domain]
                    for count, code_value in enumerate(add_code_values, start=1):
                        new_value = add_code_values[code_value]

                        print(f"\n{count}/{len(add_code_values)}) Domain and Code: {code_value} & {new_value}")
                        domains.add_code_value(db, domain, code_value, new_value)
