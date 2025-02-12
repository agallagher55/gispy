"""
~20 mins to run
"""

import arcpy
import os
import re
import logging

from datetime import datetime
from configparser import ConfigParser

config = ConfigParser()
config.read("../config.ini")

PARCEL_LOAD_DIR = config.get("GIS_DATA", "PARCEL_LOAD_DIR")
PARCEL_DATA_EXTRACT_DIR = config.get("GIS_DATA", "PARCEL_DATA_EXTRACT_DIR")
SDE_RW = config.get("GIS_DATA", "SDE_RW")
SDEADM_GSA_Polygon = config.get("GIS_DATA", "SDEADM_GSA_Polygon")

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

# Set logging level
file_handler.setLevel(logging.DEBUG)
console_handler.setLevel(logging.DEBUG)

# Create logger and add handlers
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)  # Write logs to a file
logger.addHandler(console_handler)  # print logs to the console

arcpy.env.scratchWorkspace = PARCEL_LOAD_DIR


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
    workspace_files = os.listdir(PARCEL_LOAD_DIR)

    parcels = os.path.join(
        workspace,
        [x for x in workspace_files if x.startswith("HRM") and x.endswith(".shp") and "Parcels" in x][0]
    )
    lines = os.path.join(
        workspace,
        [x for x in workspace_files if x.startswith("HRM") and x.endswith(".shp") and "Lines" in x][0]
    )
    labels = os.path.join(
        workspace,
        [x for x in workspace_files if x.startswith("HRM") and x.endswith(".shp") and "Labels" in x][0]
    )

    # Make sure date is the same as source folder
    source_folder_date = os.path.basename(PARCEL_DATA_EXTRACT_DIR).split("_")[1].replace("-", "")

    # TODO: Replace with regex?
    parcels_date = [x.strip(".shp") for x in os.path.basename(parcels).split("_") if x.strip(".shp").isdigit()][0]
    parcel_lines_date = [x.strip(".shp") for x in os.path.basename(lines).split("_") if x.strip(".shp").isdigit()][0]
    parcel_labels_date = [x.strip(".shp") for x in os.path.basename(labels).split("_") if x.strip(".shp").isdigit()][0]

    for shapefile_date in parcels_date, parcel_lines_date, parcel_labels_date:
        if shapefile_date != source_folder_date:
            error_message = f"It seems that the date of one the parcel shapefiles does not match the date of the source" \
                            f"folder. Check to make sure the data is dated the same as the folder."
            raise ValueError(error_message)

    return parcels, lines, labels


def prepare_prov_shapefiles(feature_info: dict):
    """
    CUSTOM PROJECTION FILE NEEDS TO BE AVAILABLE ON SERVER WHERE SCRIPT IS RUN
    """

    clip_parcel_label = os.path.join(PARCEL_LOAD_DIR, "Clip_Parcel_Label.shp")
    dissolve_parcel_point = os.path.join(PARCEL_LOAD_DIR, "Dissolve_Parcel_Point.shp")
    select_parcel_line = os.path.join(PARCEL_LOAD_DIR, "Select_Parcel_Line.shp")
    select_ghosted_line = os.path.join(PARCEL_LOAD_DIR, "Select_Ghosted_Line.shp")
    select_sdeadm_gsa_polygon = os.path.join(PARCEL_LOAD_DIR, "Select_SDEADM_GSA_Polygon.shp")

    out_coor_system = "PROJCS['NAD_1983_CSRS_2010_MTM_5_Nova_Scotia',GEOGCS['GCS_North_American_1983_CSRS_2010',DATUM['D_North_American_1983_CSRS',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',25500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-64.5],PARAMETER['Scale_Factor',0.9999],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]]"
    transform_method = "ATS77_to_NAD83(CSRS)2010 + NAD83_CSRS_1997_to_NAD83_CSRS_2010"
    in_coor_system = "PROJCS['ATS_1977_MTM_5_Nova_Scotia',GEOGCS['GCS_ATS_1977',DATUM['D_ATS_1977',SPHEROID['ATS_1977',6378135.0,298.257]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',5500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-64.5],PARAMETER['Scale_Factor',0.9999],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]]"

    logger.info("Preparing provincial shapefiles...")

    logger.info("Projecting features...")

    for feature in feature_info:
        projected_feature = feature_info[feature]["projected"]

        logger.info(f"\tProjecting {feature} to {projected_feature}...")

        # ERROR 000365: Invalid geographic transformation.
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
    arcpy.Select_analysis(SDEADM_GSA_Polygon, select_sdeadm_gsa_polygon, "MUN_CODE = 'HRM'")

    logger.info("Clipping parcel labels to GSA boundary...")
    arcpy.Clip_analysis(
        in_features=NAD83_SHP_Parcel_Label,
        clip_features=select_sdeadm_gsa_polygon,
        out_feature_class=clip_parcel_label
    )

    logger.info("Dissolving clipped parcel labels by PID...")
    arcpy.Dissolve_management(
        clip_parcel_label,
        dissolve_parcel_point,
        "PID",
        "DXF_LAYER FIRST;FILENAME FIRST;UPDAT_DATE FIRST",
        "MULTI_PART",
        "DISSOLVE_LINES"
    )

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
        shp_parcel_label: {"projected": NAD83_SHP_Parcel_Label}
    }

    logger.info("Preparing Province shapefile...")
    prepare_prov_shapefiles(feature_info)

    logger.info(f"{datetime.now()}")
