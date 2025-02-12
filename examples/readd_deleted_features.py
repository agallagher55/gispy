import arcpy
import os

from gispy import (
    domains,
    utils,
    attribute_rules
)

from configparser import ConfigParser

from os import getcwd, environ

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

FEATURE = "SDEADM.AST_boat_facility"
REPLICA = "SDEADM.AST_Rosde"

RESTORE_GDB = r"T:\work\giss\monthly\202406june\gallaga\AST_boatfacility\Default.gdb"
RESTORE_FEATURE = os.path.join(RESTORE_GDB, "boatfacility_june13")

# Export Attribute Rules
ATTR_RULES_CSV = r"T:\work\giss\monthly\202406june\gallaga\AST_boatfacility\BoatFacilty_AttrRules.csv"


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    print(f"\nPC Name: {PC_NAME}\n\tRunning from: {run_from}...")

    for dbs in [
        # {
        #     config.get("SERVER", "dev_rw"): config.get("SERVER", "dev_ro"),
        # },
        # [
        #     config.get("SERVER", "qa_rw"),
        # ],
        {
            config.get("SERVER", "prod_rw"): config.get("SERVER", "prod_ro"),
        },

    ]:

        if dbs:
            print(f"\nProcessing dbs: {', '.join(dbs)}...")

            for db in dbs:
                print(f"\nDATABASE: {db}")

                ro_db = dbs.get(db)

                with arcpy.EnvManager(workspace=db, preserveGlobalIds=True):

                    rules = attribute_rules.get_rules(FEATURE)

                    if rules:
                        # TODO: Turn off services

                        # Delete Attribute Rules
                        print("\nDeleting Attribute Rules...")
                        arcpy.DeleteAttributeRule_management(FEATURE, names=[x.name for x in rules])
                        print(arcpy.GetMessages())

                    # Truncate
                    print("\nTruncating feature...")
                    arcpy.DeleteFeatures_management(FEATURE)
                    print(arcpy.GetMessages())

                    print("\nTurning OFF Editor Tracking...")
                    arcpy.DisableEditorTracking_management(FEATURE)
                    print(arcpy.GetMessages())

                    # Load - preserve GlobalIDs
                    print("\nLoading feature...")
                    arcpy.Append_management(
                        inputs=RESTORE_FEATURE,
                        target=FEATURE,
                        schema_type="TEST",
                    )
                    print(arcpy.GetMessages())

                    print("\nTurning ON Editor Tracking...")
                    arcpy.EnableEditorTracking_management(
                        FEATURE,
                        "ADDBY", "ADDDATE", "MODBY", "MODDATE",
                        "NO_ADD_FIELDS",
                        "UTC"
                    )
                    print(arcpy.GetMessages())

                    # Import Attribute Rules
                    print("\nImporting Attribute Rules...")
                    arcpy.ImportAttributeRules_management(
                        FEATURE, ATTR_RULES_CSV
                    )
                    print(arcpy.GetMessages())

                    # Sync Replicas
                    print("\nSyncing Replica...")
                    arcpy.SynchronizeChanges_management(
                        geodatabase_1=db,
                        in_replica=REPLICA,
                        geodatabase_2=ro_db,
                        in_direction="FROM_GEODATABASE1_TO_2",
                        conflict_policy="IN_FAVOR_OF_GDB1",
                        reconcile="RECONCILE"
                    )
                    print(arcpy.GetMessages())

                    print("\n\nTurn ON services.\n")

