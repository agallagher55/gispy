import os
import arcpy

from area_rates import (
    AREA_RATE_FEATURES,
    AREA_RATE_FINAL_FEATURE_UPDATE_NAME,
    SDE,
    YEAR,
)

arcpy.env.overwriteOutput = True

TAX_SYSTEM = "SAP"
MAIN_WORKSPACE_DIR = r"T:\work\giss\tools\Area_Rates"


def create_workspace(season: str):
    """
    - SOURCE DATA folder will contain file geodatabase containing parcels, linnspidrelate, linnspidretire, for reference
        in future years.
    """

    folder_name = fr"v{YEAR}_{season.lower()} - {TAX_SYSTEM}"
    print(f"\nCreating folder: '{folder_name}'...")

    new_folder_path = os.path.join(MAIN_WORKSPACE_DIR, folder_name)

    os.makedirs(new_folder_path, exist_ok=True)

    # Create folder for each area rate
    for area_rate in list(AREA_RATE_FEATURES) + ["SOURCE_DATA"]:
        area_rate_basename = os.path.basename(area_rate)
        area_rate_folder = os.path.join(new_folder_path, area_rate_basename).replace("LND_area_rate_", "")

        print(f"\tCreating folder for '{area_rate_folder}'...")
        os.makedirs(area_rate_folder, exist_ok=True)

    # Create geodatabase for archiving purposes
    archive_gdb = arcpy.CreateFileGDB_management(
        out_folder_path=new_folder_path,
        out_name="final_features_archive.gdb"
    )[0]

    # Create geodatabase for source data
    sources_gdb = arcpy.CreateFileGDB_management(
        out_folder_path=new_folder_path,
        out_name="scratch.gdb"
    )[0]

    with arcpy.EnvManager(workspace=SDE):

        for table in [
            r"SDEADM.LINNS_PIDRELATE",
            r"SDEADM.LINNS_PIDAANTAX",
        ]:

            print(f"\tExporting current '{table}' table...")
            arcpy.TableToGeodatabase_conversion(
                Input_Table=table,
                Output_Geodatabase=sources_gdb
            )

        for feature in [
            r"SDEADM.LND_parcels/SDEADM.LND_parcel_polygon",
        ]:

            print(f"\tExporting current '{feature}' feature...")
            arcpy.FeatureClassToGeodatabase_conversion(
                Input_Features=[feature,],
                Output_Geodatabase=sources_gdb
        )

    return new_folder_path, archive_gdb


def archive_previous_call(archive_gdb):
    print(f"\nArchiving previous rate call table to {archive_gdb}...")

    with arcpy.EnvManager(workspace=SDE):
        final_tables = arcpy.ListTables("*_FINAL_SAP") + [AREA_RATE_FINAL_FEATURE_UPDATE_NAME]
        print(final_tables)

        for table in final_tables:
            table_name = arcpy.Describe(table).baseName.split(".")[-1]

            print(f"\tArchiving '{table_name}'...")
            arcpy.TableToGeodatabase_conversion(
                Input_Table=table,
                Output_Geodatabase=archive_gdb
            )

        # Archive parcels used during process


if __name__ == "__main__":

    new_folder_path, archive_gdb = create_workspace("SUMMER")

    archive_previous_call(archive_gdb)

