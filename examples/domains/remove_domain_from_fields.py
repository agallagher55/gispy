import arcpy

from gispy import features

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

REMOVE_DOMAINS = {
    "SDEADM.BLD_building_assetpoint": ["ADDBY", "MODBY"],
}

CURRENT_DIR = getcwd()

if __name__ == "__main__":

    from datetime import datetime

    print(datetime.now())

    for dbs in [
        [
            config.get("SERVER", "dev_rw"),
            config.get("SERVER", "dev_ro"),
        ],
        # [
        #     config.get("SERVER", "qa_rw"),
        #     config.get("SERVER", "qa_ro"),
        #     config.get("SERVER", "qa_web_ro_gdb")
        # ],
        # [config.get("SERVER", "prod_rw"), config.get("SERVER", "prod_ro"), config.get("SERVER", "prod_web_ro_gdb")],
    ]:

        print(f"\nProcessing dbs: {', '.join(dbs)}...")

        for db in dbs:
            print(f"\nDATABASE: {db}")

            with arcpy.EnvManager(workspace=db):

                for feature in REMOVE_DOMAINS:

                    remove_fields = REMOVE_DOMAINS[feature]

                    for field_name in remove_fields:

                        print(f"\nRemoving domain from field '{field_name}' on '{feature}'...")

                        arcpy.RemoveDomainFromField_management(
                            in_table=feature,
                            field_name=field_name
                        )
                        print(arcpy.GetMessages())

    print(datetime.now())
