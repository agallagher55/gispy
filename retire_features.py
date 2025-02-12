import arcpy
import os

from configparser import ConfigParser
from os import environ
from os import getcwd
from datetime import datetime

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

CURRENT_DIR = getcwd()

PC_NAME = environ['COMPUTERNAME']

# SDE_RW = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "dev_rw")
# SDE_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "dev_ro")
# GDB_WEB_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "dev_web_ro_gdb")

# SDE_RW = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "qa_rw")
# SDE_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "qa_ro")
# GDB_WEB_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "qa_web_ro_gdb")

SDE_RW = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "prod_rw")
SDE_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "prod_ro")
GDB_WEB_RO = config.get("SERVER" if "APP" in PC_NAME else "LOCAL", "prod_web_ro_gdb")

ARCHIVE_GDB = r'T:\work\giss\ArchivedData\SDE_Archive_Data.gdb'


def feature_db_roles(features, db):
    print(f"\nGetting DB roles for {', '.join(features)}...")

    # Remove prefix from features
    features = [x.split(".")[-1] for x in features]

    sql = f'''
    -- Get unique AD groups from given tables
    SELECT DISTINCT(GRANTEE) FROM
        (
            SELECT 
                perm.permission_name AS PRIVILEGE,
                user_name(perm.grantee_principal_id) AS GRANTEE,
                obj.name AS table_name
            FROM 
                sys.database_permissions AS perm
            JOIN 
                sys.objects AS obj ON perm.major_id = obj.object_id
            JOIN 
                sys.schemas AS sch ON obj.schema_id = sch.schema_id

            WHERE user_name(perm.grantee_principal_id) NOT IN ('sde', 'public') AND
                (
                    obj.name NOT LIKE '%get_ids%' AND 
                    obj.name NOT LIKE '%_evw' AND
                    perm.permission_name LIKE 'INSERT' AND 
                    obj.name NOT LIKE 'D[0-9]%' AND 
                    obj.name NOT LIKE 'a[0-9]%'
                ) and 
                obj.name IN 
                (
                    {', '.join([f"'{x}'" for x in features])}
                )
        )
    AS subquery
    ORDER BY GRANTEE
    ;
    '''

    conn = arcpy.ArcSDESQLExecute(db)

    initial_result = conn.execute(sql)

    return_type = type(initial_result)

    if return_type == list:
        results = [x[0] for x in conn.execute(sql)]

    elif return_type == str:
        results = [initial_result, ]

    else:
        results = []

    print("\tWriting results to file...")
    with open("db_roles.txt", "w") as txtfile:
        txtfile.write(f"DB Roles for {', '.join(features)}:")
        for result in results:
            txtfile.write(f"\n\t{result}")

    # TODO: also get NON-AD Group roles

    return results


def check_datawarehouse(feature: str):
    ...


def retire_features(features: list, sde_rw, sde_ro, sde_webro, delete_rw_features=False, export_to_gdb=False):
    """
    - Copy and rename (include archive date) an archive copy of the feature class to the following GDB (T:\work\giss\ArchivedData\SDE_Archive_Data.gdb)
    - Record current DB roles associated with the FC. I typically stored this in my monthly folder on the T: drive.
    - If FC is part of a replica, remove it from the replica in both RW and RO
    - If the FC is part of service, remove it from the service (talk to mike to see if you need to do anything special here) and republish the service.
    - Remove DB roles from FC
    - I typically leave the FC in the database for 2 weeks to make sure no one complains about it missing before I delete it from the database.
    - Update CMDB
    - Remove from project to WGS84 script
    :param features:
    :return:
    """

    # Copy and rename (include archive date) an archive copy of the feature class to the following GDB
    # (T:\work\giss\ArchivedData\SDE_Archive_Data.gdb)

    with arcpy.EnvManager(workspace=ARCHIVE_GDB):
        archive_features = arcpy.ListFeatureClasses() + arcpy.ListTables()

    # check if feature already exists in archive gdb first...
    if export_to_gdb:

        for feature in features:

            feature_name = feature.split('.')[-1]

            # if any([feature_name in archive_feature for archive_feature in archive_features]):
            #
            #     archived_feature = [x for x in archive_features if feature in x][0]
            #
            #     raise IndexError(f"Feature already exists in archive GDB as {archived_feature}!")

            out_feature = os.path.join(ARCHIVE_GDB, f"{feature_name}_{datetime.now().strftime('%d_%m_%Y')}")

            # only export if from PROD workspace
            if "PROD" in sde_rw.upper():
                print(f"\tExporting '{feature}' to {ARCHIVE_GDB} as {out_feature}...")

                in_feature = os.path.join(sde_rw, feature)

                # Feature class or table
                feature_type = arcpy.Describe(in_feature).dataType

                if feature_type == 'Table':
                    arcpy.ExportTable_conversion(
                        in_table=in_feature,
                        out_table=out_feature,
                    )

                else:
                    arcpy.ExportFeatures_conversion(
                        in_features=in_feature,
                        out_features=out_feature,
                        use_field_alias_as_name="NOT_USE_ALIAS",
                    )

    # Get DB roles
    roles = feature_db_roles(features, sde_rw)

    # Remove from replica
    # TODO: Check if feature is in a replica
    input("Manually unregister feature from replica in RW & RO. Hit enter once finished.")

    # Remove view privileges
    print("Removing PUBLIC view privileges...")

    for feature in features:
        print(f"\nFeature: {feature}")

        sde_feature = os.path.join(sde_rw, feature)

        for role in roles + ["PUBLIC"]:
            print(f"\tRevoking privileges for {role}...")

            try:
                arcpy.ChangePrivileges_management(
                    in_dataset=sde_feature,
                    user=role,
                    View="REVOKE",
                    Edit="REVOKE"
                )

            except arcpy.ExecuteError:
                print(arcpy.GetMessages())

            except Exception as e:
                print(e)

    # Delete from RO, WEBGIS, web_ro
    for workspace_info in (
            (sde_ro, "SDEADM."),
            (sde_webro, ""),
    ):

        db, schema = workspace_info

        for feature in features:
            delete_feature = os.path.join(db, f"{schema}{feature}")
            print(f"\nDeleting '{delete_feature}'")
            arcpy.Delete_management(delete_feature)

            print(arcpy.GetMessages())

    # Remove from WGS84 script - DONE
    # Update CMDB - DONE

    # Delete RW feature
    if delete_rw_features:

        for feature in features:
            delete_feature = os.path.join(sde_rw, f"{schema}{feature}")
            print(f"\nDeleting '{delete_feature}'")
            arcpy.Delete_management(delete_feature)

            print(arcpy.GetMessages())


if __name__ == "__main__":
    # TODO: Add to WEBGIS? web_ro?

    retired_features = [
        "SDEADM.AST_traffic_detector",
    ]

    retire_features(
        retired_features,
        SDE_RW,
        SDE_RO,
        GDB_WEB_RO,
        False
    )

