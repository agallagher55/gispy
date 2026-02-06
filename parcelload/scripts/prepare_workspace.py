"""
- *Make sure to update PARCEL_DATA_EXTRACT location in config.ini
- ~2 minutes
"""

import shutil
import arcpy
import os
import logging
import re

from configparser import ConfigParser

from datetime import datetime
from shutil import copytree

config = ConfigParser()
config.read("../config.ini")

PARCEL_DATA_EXTRACT_DIR = config.get("GIS_DATA", "PARCEL_DATA_EXTRACT_DIR")
PARCEL_LOAD_DIR = config.get("GIS_DATA", "PARCEL_LOAD_DIR")

LINNS_ALL_SDE_RW = config.get("GIS_DATA", "LINNS_ALL_SDE_RW")
PARCEL_POINT_RW = config.get("GIS_DATA", "PARCEL_POINT_RW")
PARCEL_POINT_SINGLE_RW = config.get("GIS_DATA", "PARCEL_POINT_SINGLE_RW")
SDEADM_LND_ghosted_parcel_line = config.get("GIS_DATA", "SDEADM_LND_ghosted_parcel_line")
SDEADM_LND_parcel_line = config.get("GIS_DATA", "SDEADM_LND_parcel_line")
SDEADM_LND_parcel_polygon = config.get("GIS_DATA", "SDEADM_LND_parcel_polygon")

SDE_RW = config.get("GIS_DATA", "SDE_RW")
SDEADM_GSA_POLYGON = config.get("GIS_DATA", "SDEADM_GSA_Polygon")

CURRENT_MONTH = datetime.now().strftime('%B')  # Date format YYMMDD

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

# Logging
log_dir = os.getcwd()

# File handler
logFile = log_dir + "\\script_logs.log"
file_handler = logging.FileHandler(logFile)

# Console handler
console_handler = logging.StreamHandler()

# Configure formatter
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
file_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

# Create logger and add handlers
logger = logging.getLogger(__name__)

# Set logging level
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)  # Write logs to a file
logger.addHandler(console_handler)  # logger.info logs to the console


def prepare_workspace(workspace: str, new_parcel_data_dir: str) -> dict:
    """
    Prepare the workspace by clearing old data, verifying the date match,
    copying new data, and creating a new file geodatabase.

    Args:
        workspace (str): Path to the local workspace directory.
        new_parcel_data_dir (str): Path to the source folder of new parcel data.

    Returns:
        dict: Contains paths to the prepared workspace and the new geodatabase.
    """

    logger.info(f"Preparing workspace '{workspace}'...")

    geodatabase = os.path.join(workspace, f"{CURRENT_MONTH}ParcelBackup.gdb")

    # Delete any existing files in your Scratch workspace, if present
    if os.path.exists(workspace):

        try:
            logger.info(f"\tRemoving existing workspace: {workspace}")
            shutil.rmtree(workspace)  # deletes an entire directory tree (including subdirectories under it).

        except Exception as e:
            logger.error(f"Failed to delete workspace directory: {e}")
            raise

    # Validate the month in the source folder matches the current month
    try:
        parcel_data_dir_month = re.sub('\d', '', new_parcel_data_dir.split("\\")[
            new_parcel_data_dir.split("\\").index('monthly') + 1
            ]).title()

        if parcel_data_dir_month not in CURRENT_MONTH:
            raise ValueError(
                f"Parcel Directory: {new_parcel_data_dir}, Current Month: {CURRENT_MONTH}. MAKE SURE THESE ARE THE SAME")

    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse date from folder name: {new_parcel_data_dir}")
        raise ValueError("Could not extract date from parcel data directory. Check folder naming convention.") from e

    # Transfer new parcel data to workspace
    logger.info(f"Copying parcel files from {new_parcel_data_dir} to {workspace}...")
    copytree(src=new_parcel_data_dir, dst=workspace)  # creates any folders that don't already exist.

    # Create a file geodatabase "{current_month}ParcelBackup.gdb"
    logger.info(f"Creating backup geodatabase...")
    arcpy.CreateFileGDB_management(
        out_folder_path=workspace,
        out_name=f"{CURRENT_MONTH}ParcelBackup.gdb"
    )

    return {
        "workspace": workspace,
        "geodatabase": geodatabase
    }


def backup_features(geodatabase: str):
    """
    This function takes in a geodatabase file path.
    It exports the current parcel related feature classes and tables to the geodatabase.
    It then returns the list of input feature classes and tables.

    :return: List of input feature classes and tables
    """

    features = [
        PARCEL_POINT_RW,
        SDEADM_LND_ghosted_parcel_line,
        SDEADM_LND_parcel_line,
        SDEADM_LND_parcel_polygon,
        PARCEL_POINT_SINGLE_RW,
    ]

    tables = [LINNS_ALL_SDE_RW, ]

    logger.info(f"Exporting current SDE features to '{geodatabase}'...")

    for feature in features:
        try:
            arcpy.FeatureClassToGeodatabase_conversion(
                Input_Features=feature,
                Output_Geodatabase=geodatabase
            )
        except arcpy.ExecuteError:
            arcpy_msg = arcpy.GetMessages(2)
            logger.info(f"Error occurred while exporting {feature}. \nError: {arcpy_msg}")

    logger.info(f"Exporting {', '.join(tables)} to {geodatabase}...")
    for table in tables:
        try:
            arcpy.TableToGeodatabase_conversion(
                Input_Table=table,
                Output_Geodatabase=geodatabase
            )
        except arcpy.ExecuteError:
            arcpy_msg = arcpy.GetMessages(2)
            logger.info(f"Error occurred while exporting {table}. \nError: {arcpy_msg}")

    with arcpy.EnvManager(workspace=geodatabase):
        exported_features = arcpy.ListFeatureClasses()
        exported_tables = arcpy.ListTables()

        logger.info(
            f"\nExported features + tables: {', '.join(sorted(exported_features + exported_tables))}"
            f"\n\tShould be: LINNS_ALL, ghosted parcel lines, parcel lines, parcel points, parcel point single,"
            f" and parcel polygon"
        )

    return features + tables


def data_check(new_parcels: str):
    """
    Compare the count of the new parcels feature vs the current parcel feature

    :param new_parcels: shapefile
    :return:
    """

    logger.info("Performing data checks...")
    logger.info("Comparing new parcels with currently existing...")

    sde_parcels = os.path.join(SDE_RW, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

    new_parcels_row_count = int(arcpy.GetCount_management(new_parcels)[0])
    current_parcels_row_count = int(arcpy.GetCount_management(sde_parcels)[0])

    # TODO: Log this;
    logger.info(f"\tRow count for NEW parcels: {new_parcels_row_count}")
    logger.info(f"\tRow count for SDE parcels: {current_parcels_row_count}")

    if current_parcels_row_count > new_parcels_row_count:
        error_msg = f"New parcels have a lower row count than SDE parcels. Check data should be uploaded."
        raise ValueError(error_msg)

    logger.info(
        f"{new_parcels_row_count - current_parcels_row_count} ADDITIONAL parcels will be added to the parcel layer in this month's update!")

    return new_parcels_row_count, current_parcels_row_count


def query_prov_shapefiles(workspace=PARCEL_LOAD_DIR):
    print("Querying Provincial shapefiles...")

    workspace_files = os.listdir(PARCEL_LOAD_DIR)

    hrm_shp_files = [x for x in workspace_files if x.startswith("HRM") and x.endswith(".shp")]

    parcels = os.path.join(
        workspace,
        [x for x in hrm_shp_files if "PARCELS" in x.upper()][0]
    )
    lines = os.path.join(
        workspace,
        [x for x in hrm_shp_files if "LINES" in x.upper()][0]
    )

    try:
        labels = os.path.join(
            workspace,
            [x for x in hrm_shp_files if "Labels" in x][0]  # [x for x in workspace_files if x.startswith("HRM") and x.endswith(".shp") and "Labels" in x][0]
        )

    except IndexError:
        labels = None

    # Make sure date is the same as source folder - NO LONGER APPLICABLE (JULY 2024), FOLDER IS GIVEN RANDOM NUMBER
    source_folder_date = os.path.basename(PARCEL_DATA_EXTRACT_DIR).split("_")[1].replace("-", "")

    # TODO: Pull year and month from folder
    # Regex to extract year and month
    pattern = r'\\(\d{4})(\d{2})'

    # Search for the pattern
    match = re.search(pattern, PARCEL_DATA_EXTRACT_DIR)

    if match:
        year = match.group(1)  # Extract the year
        month = match.group(2)  # Extract the month number

    # TODO: Replace with regex?

    parcels_date = [x.strip(".shp") for x in os.path.basename(parcels).split("_") if x.strip(".shp").isdigit()][0]
    parcel_lines_date = [x.strip(".shp") for x in os.path.basename(lines).split("_") if x.strip(".shp").isdigit()][0]

    for shapefile_date in parcels_date, parcel_lines_date:

        print(f"Shapefile date: {shapefile_date}")

        if f"{year}{month}" not in shapefile_date:

        # if shapefile_date != source_folder_date:

            error_message = f"It seems that the date of one the parcel shapefiles does not match the date of the source" \
                            f"folder. Check to make sure the data is dated the same as the folder."

            print(f"year: {year}")
            print(f"month: {month}")
            print(f"{year}{month} not in {shapefile_date}")

            raise ValueError(error_message)

    return parcels, lines, labels


def prepare_prov_shapefiles(feature_info: dict):

    """
    CUSTOM PROJECTION FILE NEEDS TO BE AVAILABLE ON SERVER WHERE SCRIPT IS RUN
    """

    select_parcel_line = os.path.join(PARCEL_LOAD_DIR, "Select_Parcel_Line.shp")
    select_ghosted_line = os.path.join(PARCEL_LOAD_DIR, "Select_Ghosted_Line.shp")
    select_sdeadm_gsa_polygon = os.path.join(PARCEL_LOAD_DIR, "Select_SDEADM_GSA_Polygon.shp")

    in_coor_system = "PROJCS['ATS_1977_MTM_5_Nova_Scotia',GEOGCS['GCS_ATS_1977',DATUM['D_ATS_1977',SPHEROID['ATS_1977',6378135.0,298.257]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',5500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-64.5],PARAMETER['Scale_Factor',0.9999],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]]"
    in_coor_system = 'PROJCS["NAD_1983_CSRS_UTM_Zone_20N",GEOGCS["GCS_North_American_1983_CSRS",DATUM["D_North_American_1983_CSRS",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",-63.0],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]'

    out_coor_system = "PROJCS['NAD_1983_CSRS_2010_MTM_5_Nova_Scotia',GEOGCS['GCS_North_American_1983_CSRS_2010',DATUM['D_North_American_1983_CSRS',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',25500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-64.5],PARAMETER['Scale_Factor',0.9999],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]]"

    transform_method = "ATS77_to_NAD83(CSRS)2010 + NAD83_CSRS_1997_to_NAD83_CSRS_2010"
    transform_method = "NAD83_CSRS_1997_to_NAD83_CSRS_2010"

    logger.info("Preparing provincial shapefiles...")

    logger.info("Projecting features...")

    for feature in feature_info:

        projected_feature = feature_info[feature]["projected"]

        logger.info(f"Projecting {feature} to {projected_feature}...")

        # ERROR 000365: If invalid geographic transformation.
        # FIXED: Copy over transformation files from
        # C:\Users\{user}\AppData\Roaming\ESRI\Desktop10.8\ArcToolbox\CustomTransformations to
        # C:\Users\{user}\AppData\Roaming\ESRI\ArcGISPro\ArcToolbox\CustomTransformations

        arcpy.Project_management(
            in_dataset=feature,
            out_dataset=projected_feature,
            out_coor_system=out_coor_system,
            transform_method=transform_method,
            in_coor_system=in_coor_system,
            preserve_shape="NO_PRESERVE_SHAPE",
            max_deviation="#",
            vertical="NO_VERTICAL"
        )

    logger.info("Creating point products...")
    arcpy.Select_analysis(SDEADM_GSA_POLYGON, select_sdeadm_gsa_polygon, "MUN_CODE = 'HRM'")

    logger.info("Creating line products...")
    arcpy.Select_analysis(NAD83_SHP_Parcel_Line, select_parcel_line, "THEME_NO = 1001")
    arcpy.Select_analysis(NAD83_SHP_Parcel_Line, select_ghosted_line, "THEME_NO = 4700")

    ghosted_lines_count = int(arcpy.GetCount_management(select_ghosted_line)[0])
    if ghosted_lines_count == 0:
        logger.info(f"NO GHOSTED LINES FOUND.")

    logger.info("Repairing geometry...")
    # Repair Geometry twice per feature
    for i in range(2):
        arcpy.RepairGeometry_management(NAD83_SHP_Parcel_Polygon)
        arcpy.RepairGeometry_management(select_parcel_line)
        arcpy.RepairGeometry_management(select_ghosted_line)

    # Process: Add Fields
    add_field_features = [
        NAD83_SHP_Parcel_Polygon,
        select_parcel_line
    ]

    def add_and_calculate_fields(feature):
        """
        Add and calculate specified fields for a given feature.
        """

        # Define a dictionary for fields with their properties and calculation values
        fields_dict = {
            "FCODE": {"type": "TEXT", "length": 12, "calculation": "!DXF_LAYER!"},
            "SOURCE": {"type": "TEXT", "length": 12, "calculation": "\"LIC-PROPMAP\""},
            "SACC": {"type": "TEXT", "length": 2, "calculation": "\"DG\""},
            "SDATE": {"type": "DATE",
                      "calculation": f"datetime({datetime.now().strftime('%Y,%m,%d,%H,%M,%S')})"},
            "OPERATOR": {"type": "TEXT", "length": 8, "calculation": "\"NSGC\""}
        }

        for field, properties in fields_dict.items():
            logger.info(f'Adding {field} field to {feature}')
            arcpy.AddField_management(feature, field, properties["type"], "", "", properties.get("length", ""), "",
                                      "NULLABLE", "NON_REQUIRED")

            logger.info(f'\tCalculating {field} field on {feature}')
            arcpy.CalculateField_management(feature, field, properties["calculation"], "PYTHON_9.3", "")

    logger.info("Adding fields...")
    for feature in add_field_features:
        logger.info('Adding FCODE field to ' + feature)
        arcpy.AddField_management(feature, "FCODE", "TEXT", "", "", 12, "", "NULLABLE", "NON_REQUIRED")

        logger.info('Adding SOURCE field to ' + feature)
        arcpy.AddField_management(feature, "SOURCE", "TEXT", "", "", 12, "", "NULLABLE", "NON_REQUIRED")

        logger.info('Adding SACC field to ' + feature)
        arcpy.AddField_management(feature, "SACC", "TEXT", "", "", 2, "", "NULLABLE", "NON_REQUIRED")

        logger.info('Adding SDATE field to ' + feature)
        arcpy.AddField_management(feature, "SDATE", "DATE", "", "", "", "", "NULLABLE", "NON_REQUIRED")

        logger.info('Adding OPERATOR field to ' + feature)
        arcpy.AddField_management(feature, "OPERATOR", "TEXT", "", "", 8, "", "NULLABLE", "NON_REQUIRED")

        logger.info('\tCalculating FCODE field on ' + feature)
        arcpy.CalculateField_management(feature, "FCODE", "!DXF_LAYER!", "PYTHON_9.3", "")

        logger.info('\tCalculating SOURCE field on ' + feature)
        arcpy.CalculateField_management(feature, "SOURCE", "\"LIC-PROPMAP\"", "PYTHON_9.3", "")

        logger.info('\tCalculating SACC field on ' + feature)
        arcpy.CalculateField_management(feature, "SACC", "\"DG\"", "PYTHON_9.3", "")

        logger.info('\tCalculating SDATE field on ' + feature)
        arcpy.CalculateField_management(feature, "SDATE", "datetime.now()", "PYTHON_9.3", "")

        logger.info('\tCalculating OPERATOR field on ' + feature)
        arcpy.CalculateField_management(feature, "OPERATOR", "\"NSGC\"", "PYTHON_9.3", "")
        # TODO: Combine adding and calculating field to one step

    logger.info("Finished adding and calculating fields.")

    # Process: Rename the parcel polygon shapefile for the cache process
    if NAD83_SHP_Parcel_Polygon != os.path.join(PARCEL_LOAD_DIR, "Parcel_Polygon.shp"):
        logger.info(f"Renaming '{NAD83_SHP_Parcel_Polygon}' to 'Parcel_Polygon.shp'...")

        # The output name must be unique. If it is not, an error message is reported,
        # even if the geo-processing overwrite output environment is set to true.
        arcpy.Rename_management(NAD83_SHP_Parcel_Polygon, "Parcel_Polygon.shp")


if __name__ == "__main__":

    logger.info(f"{datetime.now()}")
    
    prepared_workspace = prepare_workspace(PARCEL_LOAD_DIR, PARCEL_DATA_EXTRACT_DIR)

    backed_up_features = backup_features(prepared_workspace['geodatabase'])

    # Section 2
    # Local variables:
    NAD83_SHP_Parcel_Polygon = os.path.join(PARCEL_LOAD_DIR, "HRM_Parcels_MTM_NAD83.shp")
    NAD83_SHP_Parcel_Line = os.path.join(PARCEL_LOAD_DIR, "HRM_Lines_MTM_NAD83.shp")
    NAD83_SHP_Parcel_Label = os.path.join(PARCEL_LOAD_DIR, "HRM_Labels_MTM_NAD83.shp")

    logger.info("Querying Province shapefile...")
    shp_parcel_polygon, shp_parcel_line, shp_parcel_label = query_prov_shapefiles(PARCEL_LOAD_DIR)

    logger.info("Performing data check...")
    data_check(shp_parcel_polygon)

    feature_info = {
        shp_parcel_polygon: {"projected": NAD83_SHP_Parcel_Polygon},
        shp_parcel_line: {"projected": NAD83_SHP_Parcel_Line},
    }

    logger.info("Preparing Province shapefile...")
    prepare_prov_shapefiles(feature_info)
    
    logger.info(f"{datetime.now()}")
