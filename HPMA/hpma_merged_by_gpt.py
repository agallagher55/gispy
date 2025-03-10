import arcpy
import os
import sys
import datetime
import traceback
import logging
import re
from configparser import ConfigParser

# Enable overwriting and disable log history in ArcPy
arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

# Load Configurations
config = ConfigParser()
config.read("config.ini")

# Logging Setup
log_dir: str = config.get('LOGGING', 'logDir', fallback=os.getcwd())
log_file: str = os.path.join(log_dir, "script_logs.log")
logging.basicConfig(level=logging.DEBUG, filename=log_file, filemode='w', 
                    format='%(asctime)s | %(levelname)s | %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# Database Paths (Modify as needed)
SDE: str = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
GDB_PATH: str = os.path.join(os.getcwd(), "Processed_Data.gdb")
TRN_STREET_SDE: str = os.path.join(SDE, "SDEADM.TRN_street")
HPMA_RATINGS_SDE: str = os.path.join(SDE, "SDEADM.AST_hpma_rd_condit_rating")

TRN_street: str = os.path.join(GDB_PATH, "TRN_street")
HPMA_ratings: str = os.path.join(GDB_PATH, "HPMA_ratings")
TRN_street_Points: str = os.path.join(GDB_PATH, "TRN_street_Points")
HPMA_Point: str = os.path.join(GDB_PATH, "HPMA_Point")
Output_Join: str = os.path.join(GDB_PATH, "Street_HPMA_Join")
Final_Ratings: str = os.path.join(GDB_PATH, "TRN_Street_HPMA_Ratings")


def setup_workspace(geodatabase: str) -> tuple[str, str]:
    """Sets up the workspace by creating a geodatabase and copying necessary datasets."""
    if not arcpy.Exists(geodatabase):
        arcpy.CreateFileGDB_management(os.getcwd(), "Processed_Data")
        logging.info("Created new file geodatabase")

    # Copy datasets if they don't already exist in GDB
    trn_street_local: str = os.path.join(geodatabase, "TRN_street")
    hpma_ratings_local: str = os.path.join(geodatabase, "HPMA_ratings")
    
    if not arcpy.Exists(trn_street_local):
        arcpy.FeatureClassToFeatureClass_conversion(TRN_STREET_SDE, geodatabase, "TRN_street")
        logging.info("Copied TRN_street to local workspace")
    
    if not arcpy.Exists(hpma_ratings_local):
        arcpy.FeatureClassToFeatureClass_conversion(HPMA_RATINGS_SDE, geodatabase, "HPMA_ratings")
        logging.info("Copied HPMA_ratings to local workspace")
    
    return trn_street_local, hpma_ratings_local


def filter_streets(trn_street_local: str) -> str:
    """Filters the TRN_street dataset to include only HRM-owned and Non-Accepted roads, excluding turning lanes."""
    filtered_streets: str = os.path.join(os.path.dirname(trn_street_local), "Filtered_TRN_street")
    where_clause: str = "OWN IN ('HRM', 'NA') AND FLAGS NOT IN ('TL', 'TL ZAG', 'TL UIMSR', 'RNV TL', 'NRR TL', 'NAR TL ZAG', 'GSA NRR TL', 'GNP TL', 'DSN TL')"
    arcpy.Select_analysis(trn_street_local, filtered_streets, where_clause)
    logging.info("Filtered TRN_street dataset")
    return filtered_streets


def generate_midpoints(filtered_streets: str, hpma_ratings_local: str) -> tuple[str, str]:
    """Generates midpoint feature classes along road segments and HPMA condition ratings."""
    street_midpoints: str = os.path.join(os.path.dirname(filtered_streets), "Street_Midpoints")
    hpma_midpoints: str = os.path.join(os.path.dirname(hpma_ratings_local), "HPMA_Midpoints")
    arcpy.GeneratePointsAlongLines_management(filtered_streets, street_midpoints, "PERCENTAGE", None, 50)
    arcpy.GeneratePointsAlongLines_management(hpma_ratings_local, hpma_midpoints, "PERCENTAGE", None, 50)
    logging.info("Generated midpoint features for streets and HPMA data")
    return street_midpoints, hpma_midpoints


def perform_spatial_join(street_midpoints: str, hpma_midpoints: str) -> str:
    """Performs a spatial join between road midpoints and HPMA condition data."""
    output_join: str = os.path.join(os.path.dirname(street_midpoints), "Street_HPMA_Join")
    arcpy.SpatialJoin_analysis(street_midpoints, hpma_midpoints, output_join, "JOIN_ONE_TO_ONE", "KEEP_ALL", None, "CLOSEST", "10 Meters", "DIST")
    logging.info("Performed spatial join between TRN_street and HPMA data")
    return output_join


def clean_attributes(output_join: str) -> str:
    """Cleans HWY_ID field by removing unnecessary characters."""
    cleaned_output: str = os.path.join(os.path.dirname(output_join), "Cleaned_Street_HPMA_Join")
    code_block: str = '''import re\ndef update_hwyID(HWY_ID):\n    return re.sub(r"\ \[.*\]", "", HWY_ID)'''
    expression: str = "update_hwyID(!HWY_ID!)"
    arcpy.CalculateField_management(output_join, "HWY_ID", expression, "PYTHON_9.3", code_block)
    logging.info("Cleaned HWY_ID attributes")
    return cleaned_output


def append_final_data(cleaned_output: str) -> None:
    """Truncates and appends data to the final ratings dataset."""
    arcpy.TruncateTable_management(Final_Ratings)
    arcpy.Append_management(cleaned_output, Final_Ratings, "NO_TEST")
    logging.info("Appended cleaned data to TRN_Street_HPMA_Ratings")


if __name__ == "__main__":
    try:
        trn_street_local, hpma_ratings_local = setup_workspace(GDB_PATH)
        filtered_streets = filter_streets(trn_street_local)
        street_midpoints, hpma_midpoints = generate_midpoints(filtered_streets, hpma_ratings_local)
        output_join = perform_spatial_join(street_midpoints, hpma_midpoints)
        cleaned_output = clean_attributes(output_join)
        append_final_data(cleaned_output)
        logging.info("Processing completed successfully!")
    except arcpy.ExecuteError:
        logging.error(arcpy.GetMessages(2))
    except Exception as e:
        logging.error(traceback.format_exc())
