import arcpy

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

ADD_DOMAINS = {
    "SDEADM.E_PavementDistress2016": {
        "COLLECTED_LANE": "TRNLRS_xsp",
        "SOURCE": "RTE_source",
        "SACC": "SNF_source",
    },
    "SDEADM.E_PavementDistress2018": {
        "COLLECTED_LANE": "TRNLRS_xsp",
        "SOURCE": "RTE_source",
        "SACC": "SNF_source"
    },
    "SDEADM.E_PavementDistress2020": {
        "COLLECTED_LANE": "TRNLRS_xsp",
        "SOURCE": "RTE_source",
        "SACC": "SNF_source",
    },
    "SDEADM.E_PavementDistress2022": {
        "COLLECTED_LANE": "TRNLRS_xsp",
        "SOURCE": "RTE_source",
        "SACC": "SNF_source",
    },
    "SDEADM.E_PavementDistress2024": {
        "COLLECTED_LANE": "TRNLRS_xsp",
        "SOURCE": "RTE_source",
        "SACC": "SNF_source",
    },
}

CURRENT_DIR = getcwd()

if __name__ == "__main__":
    from datetime import datetime

    print(datetime.now())

    for dbs in [
        # [utils.create_fgdb(CURRENT_DIR)],
        # [
        # config.get("SERVER", "dev_rw"),
        # config.get("SERVER", "dev_ro"),
        # config.get("SERVER", "dev_web_ro_gdb")
        # ],
        # [
            # config.get("SERVER", "qa_rw"),
            # config.get("SERVER", "qa_ro"),
            # config.get("SERVER", "qa_web_ro_gdb"),
            # r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde",
        # ],
        [
        # config.get("SERVER", "prod_rw"),
        # config.get("SERVER", "prod_ro"),
        # config.get("SERVER", "prod_web_ro_gdb"),
            r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde",
        ],
    ]:
        # r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde",
        #

        print(f"\nProcessing dbs: {', '.join(dbs)}...")

        for db in dbs:
            print(f"\nDATABASE: {db}")

            with arcpy.EnvManager(workspace=db):

                for feature in ADD_DOMAINS:
                    print(f"\n{feature}")

                    domain_info = ADD_DOMAINS[feature]

                    for field in domain_info:
                        domain = domain_info[field]

                        print(f"\tAssigning {domain} to {field}...")
                        arcpy.AssignDomainToField_management(
                            in_table=feature,
                            field_name=field,
                            domain_name=domain,
                        )

    print(datetime.now())
