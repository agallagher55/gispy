"""
Date:
"""

import arcpy
import os
import sys
import datetime
import time
import traceback
import logging

import utils

from configparser import ConfigParser

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

# Config Parser
config = ConfigParser()
config.read("E:\\HRM\\Scripts\\Python\\config.ini")

# Logging
log_dir = config.get('LOGGING', 'logDir')
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
logger = logging.getLogger('')
logger.addHandler(file_handler)  # Write logs to a file
logger.addHandler(console_handler)  # logger.info logs to the console

# Variables
SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"


# Functions
def setup_workspace(output_gdb, sde_workspace, hpma_source_feature):
    """
    1)	Create a new file geodatabase, adding a copy of TRN_street and the HPMA Extract.
        a)	Note: the extract from Scott may require a re-projection,
                    as I believe the HPMA system is referencing the ATS77 projection.
        b)	Data objects in SDE have a projection of NAD_1983_CSRS_2010_MTM_5_Nova_Scotia.

    :param geodatbase:
    :param sde_workspace:
    :param hpma_source_feature:
    :return:
    """

    sde_streets = os.path.join(sde_workspace, "SDEADM.TRN_streets_routes", "SDEADM.TRN_street")
    sde_ast_hpma_ratings = os.path.join(sde_workspace, "SDEADM.AST_hpma_rd_condit_rating")

    gdb_streets = os.path.join(output_gdb, "TRN_streets")
    gdb_ast_hpma_ratings = os.path.join(output_gdb, "AST_hpma_rd_condit_rating")
    local_hpma_data = os.path.join(output_gdb, "HPMA_ratings")

    print("\nPreparing workspace...")

    if not arcpy.Exists(output_gdb):
        print("\tCreating local geodatabase...")
        output_gdb = utils.create_fgdb()

    print("\tExporting streets to local workspace...")
    local_streets = arcpy.FeatureClassToFeatureClass_conversion(
        in_features=sde_streets,
        out_path=output_gdb,
        out_name=os.path.basename(gdb_streets)
    )[0]

    with arcpy.EnvManager(preserveGlobalIds=True):
        print("\tExporting AST_hpma_rd_condit_rating feature to local workspace...")
        local_ast_hpma_ratings = arcpy.FeatureClassToFeatureClass_conversion(
            in_features=sde_ast_hpma_ratings,
            out_path=output_gdb,
            out_name=os.path.basename(gdb_ast_hpma_ratings)
        )[0]

    print("\tExporting HPMA source feature to local workspace...")
    arcpy.FeatureClassToFeatureClass_conversion(
        in_features=hpma_source_feature,
        out_path=output_gdb,
        out_name=os.path.basename(local_hpma_data)
    )

    print("\nProjecting HPMA data to MTM and exporting result...")
    local_hpma_data = arcpy.Project_management(
        hpma_source_feature,
        local_hpma_data,
        'PROJCS["NAD_1983_CSRS_2010_MTM_5_Nova_Scotia",GEOGCS["GCS_North_American_1983_CSRS_2010",DATUM["D_North_American_1983_CSRS",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",25500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",-64.5],PARAMETER["Scale_Factor",0.9999],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]',
        "'ATS77_to_NAD83(CSRS)2010 + NAD83_CSRS_1997_to_NAD83_CSRS_2010'",
        'PROJCS["ATS_1977_MTM_5_Nova_Scotia",GEOGCS["GCS_ATS_1977",DATUM["D_ATS_1977",SPHEROID["ATS_1977",6378135.0,298.257]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",5500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",-64.5],PARAMETER["Scale_Factor",0.9999],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]',
        "NO_PRESERVE_SHAPE",
        None,
        "NO_VERTICAL"
    )[0]

    # Add fields: OWN, LANECOUNT
    local_hpma_field_info = {
        "OWN": {
            "field_type": "TEXT",
            "length": "4",
            "alias": "#",
            "nullable": "NULLABLE",
        },
        "LANECOUNT": {
            "field_type": "SHORT",
            "length": "#",
            "alias": "Lane Count",
            "nullable": "NULLABLE",
        },
        "TEMP_ID": {
            "field_type": "SHORT",
            "length": "#",
            "alias": "Temporary ID",
            "nullable": "NULLABLE",
        },
    }

    for field in local_hpma_field_info:

        arcpy.AddField_management(
            in_table=local_hpma_data,
            field_name=field,
            field_type=local_hpma_field_info[field]["field_type"],
            field_length=local_hpma_field_info[field]["length"],
            field_alias=local_hpma_field_info[field]["alias"],
            field_is_nullable=local_hpma_field_info[field]["nullable"]
        )
        print(arcpy.GetMessages())

    return local_streets, local_hpma_data, local_ast_hpma_ratings


def filter_streets(streets_feature, output_workspace):

    streets_sql = f"OWN IN ('HRM', 'NA') AND FLAGS NOT IN ( 'TL' , 'TL ZAG' , 'TL UIMSR' , 'RNV TL', 'NRR TL', 'NAR TL ZAG', 'GSA NRR TL', 'GNP TL', 'DSN TL')"

    print("\nFiltering streets feature...")

    filtered_streets = arcpy.Select_analysis(
        in_features=streets_feature,
        out_feature_class=os.path.join(output_workspace, "TRN_street_HRMandNA_noTLflag"),
        where_clause=streets_sql
    )[0]

    return filtered_streets


def analyze_features(filtered_streets, hpma_feature, output_workspace, local_ast_hpma_rd_condit_ratings):

    ########################################
    # GET STREETS DATA WITH HPMA DATA
    ########################################

    arcpy.CalculateField_management(
        local_ast_hpma_rd_condit_ratings,
        "TEMP_ID",
        "!OBJECTID!",
        "PYTHON3",
        '',
        "SHORT",
        "NO_ENFORCE_DOMAINS"
    )

    # Get midpoint of streets (Step 4 in documentation)
    street_midpoints = arcpy.GeneratePointsAlongLines_management(
        filtered_streets,
        os.path.join(output_workspace, os.path.basename(filtered_streets) + "_midpoints"),
        "PERCENTAGE",
        None,
        50,
        None
    )[0]

    # TODO: where is this in the instructions?
    pave_conditions_midpoints = arcpy.GeneratePointsAlongLines_management(
        hpma_feature,  # local_ast_hpma_rd_condit_ratings,  # TODO: Change this to input source PQI data?
        os.path.join(output_workspace, "pave_conditions_midpoints"),
        "PERCENTAGE",
        None,
        50,
        None
    )[0]

    # ==== SPATIAL JOINS ==== #
    print("\nPerforming Spatial Joins...")

    print("Getting nearest street midpoints for HPMA data...")
    # Add TRN_street data to this year's ratings
    trn_streets_hpma = arcpy.SpatialJoin_analysis(
        street_midpoints,  # hpma_feature
        pave_conditions_midpoints,
        os.path.join(output_workspace, r"trn_street_midpoints_w_hpma"),
        "JOIN_ONE_TO_ONE",
        "KEEP_ALL",  # "KEEP_COMMON",
        match_option="CLOSEST",
        search_radius="100 Meters",  # INCREASED from 10, because midpoints were getting too far apart - ~700 records weren't getting a PCI score
        distance_field_name="DIST"
    )[0]

    # TODO: load AST_HPMA_rd_condit_data

    # trn_streets_hpma_filtered = arcpy.Select_analysis(
    #     trn_streets_hpma,
    #     os.path.join(output_workspace, "trn_street_midpoints_w_hpma_filtered"),
    #     "Join_Count = 1"
    # )[0]
    #
    # # Add existing pavement condition data to this year's ratings
    # # Get pavement segment GlobalIDs  # TODO: This will only account for segments that already exist?
    # # Get closes pavement condition segment geometry
    # # TODO: PCI YEAR GETS LOST HERE
    #
    # second_midpoints_sjoin = arcpy.SpatialJoin_analysis(
    #     pave_conditions_midpoints,
    #     trn_streets_hpma_filtered,
    #     r"T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\second_midpoints_sjoin",
    #     "JOIN_ONE_TO_ONE",
    #     "KEEP_COMMON",
    #     'NUM "Route Number" true true false 4 Long 0 0,First,#,pavement_condition_midpoints,NUM,-1,-1;HWY_ID "Street Name" true true false 32 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,HWY_ID,0,32;BEGIN_DESC "From Street" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,BEGIN_DESC,0,50;END_DESC "To Street" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,END_DESC,0,50;BEGIN_REFP "Start Km Limit of section" true true false 8 Double 0 0,First,#,pavement_condition_midpoints,BEGIN_REFP,-1,-1;END_REFP "End KM Limit of section" true true false 8 Double 0 0,First,#,pavement_condition_midpoints,END_REFP,-1,-1;DISTRICT "District" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,DISTRICT,-1,-1;FUNC_CLASS "Street Class" true true false 3 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FUNC_CLASS,0,3;ADMIN_SYS "Owner" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,OWN,0,4;LANES "Number of Lanes" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,LANECOUNT,-1,-1;LENGTH "Length" true true false 8 Double 0 0,First,#,pavement_condition_midpoints,LENGTH,-1,-1;WIDTH "Width" true true false 8 Double 0 0,First,#,pavement_condition_midpoints,WIDTH,-1,-1;PAVETYPE "Material" true true false 3 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PAVETYPE,0,3;PCI_YEAR "PQI Rating Year" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PCI_YEAR,-1,-1;PCI_MRM "PQI Rating" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PQI_MRM,-1,-1;Shape_Length "Shape_Length" false true false 8 Double 0 0,First,#,pavement_condition_midpoints,Shape_Length,-1,-1;Join_Count "Join_Count" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,Join_Count,-1,-1;TARGET_FID "TARGET_FID" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TARGET_FID,-1,-1;ROUTENUM "ROUTENUM" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,ROUTENUM,-1,-1;BEGIN_MILE "BEGIN_MILE" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma_filtered,BEGIN_MILE,-1,-1;END_MILE "END_MILE" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma_filtered,END_MILE,-1,-1;PQI_MRM "PQI_MRM" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PQI_MRM,-1,-1;CONDITION "CONDITION" true true false 16 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,CONDITION,0,16;OWN "OWN" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,OWN,0,4;LANECOUNT "Lane Count" true true false 2 Short 0 0,First,#,trn_street_midpoints_w_hpma_filtered,LANECOUNT,-1,-1;FCODE "FCODE" true true false 12 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FCODE,0,12;STR_NAME "STR_NAME" true true false 40 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_NAME,0,40;STR_TYPE "STR_TYPE" true true false 6 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_TYPE,0,6;FULL_NAME "FULL_NAME" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FULL_NAME,0,50;MUN_CODE "MUN_CODE" true true false 3 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,MUN_CODE,0,3;FROM_STR "FROM_STR" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FROM_STR,0,50;TO_STR "TO_STR" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TO_STR,0,50;STR_DIR "STR_DIR" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_DIR,0,4;STR_STATUS "STR_STATUS" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_STATUS,0,4;ST_CLASS "ST_CLASS" true true false 40 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,ST_CLASS,0,40;OWN_1 "OWN" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,OWN_1,0,4;MAINTENANCE "Winter Maintenance" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,MAINTENANCE,0,4;DATE_ACCEPT "DATE_ACCEPT" true true false 8 Date 0 0,First,#,trn_street_midpoints_w_hpma_filtered,DATE_ACCEPT,-1,-1;FROM_ELEV "FROM_ELEV" true true false 2 Short 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FROM_ELEV,-1,-1;TO_ELEV "TO_ELEV" true true false 2 Short 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TO_ELEV,-1,-1;STR_REM "STR_REM" true true false 100 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_REM,0,100;PSAB_CODE "PSAB_CODE" true true false 12 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PSAB_CODE,0,12;FLAGS "FLAGS" true true false 35 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FLAGS,0,35;ACC "ACC" true true false 5 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,ACC,0,5;DATE_ACT "DATE_ACT" true true false 8 Date 0 0,First,#,trn_street_midpoints_w_hpma_filtered,DATE_ACT,-1,-1;SYS_DATE "SYS_DATE" true true false 8 Date 0 0,First,#,trn_street_midpoints_w_hpma_filtered,SYS_DATE,-1,-1;FDMID "FDMID" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FDMID,-1,-1;ROUTE_ID "ROUTE_ID" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,ROUTE_ID,-1,-1;FROM_LEFT "FROM_LEFT" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FROM_LEFT,-1,-1;TO_LEFT "TO_LEFT" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TO_LEFT,-1,-1;FROM_RIGHT "FROM_RIGHT" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,FROM_RIGHT,-1,-1;TO_RIGHT "TO_RIGHT" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TO_RIGHT,-1,-1;OLD_FDMID "OLD_FDMID" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,OLD_FDMID,-1,-1;GSA_LEFT "Left Community" true true false 40 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,GSA_LEFT,0,40;GSA_RIGHT "Right Community" true true false 40 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,GSA_RIGHT,0,40;PAR_LEFT "Left Parity" true true false 10 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PAR_LEFT,0,10;PAR_RIGHT "Right Parity" true true false 10 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,PAR_RIGHT,0,10;STR_CODE_L "Left Street Code" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_CODE_L,-1,-1;STR_CODE_R "Right Street Code" true true false 4 Long 0 0,First,#,trn_street_midpoints_w_hpma_filtered,STR_CODE_R,-1,-1;ASSETID "Asset ID" true true false 50 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,ASSETID,0,50;MAINTSUMMER "Summer Maintenance" true true false 4 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,MAINTSUMMER,0,4;LANECOUNT_1 "Lane Count" true true false 2 Short 0 0,First,#,trn_street_midpoints_w_hpma_filtered,LANECOUNT_1,-1,-1;TECH_MOD "Modified by" true true false 32 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TECH_MOD,0,32;TECH_ACT "Added by" true true false 32 Text 0 0,First,#,trn_street_midpoints_w_hpma_filtered,TECH_ACT,0,32;Shape_Length_1 "Shape_Length" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma_filtered,Shape_Length_1,-1,-1',
    #     "CLOSEST",
    #     "10 Meters",
    #     ''
    # )[0]
    #
    # # TODO: Spatial join with linear pavement data to midpoints
    # arcpy.DeleteField_management(
    #     local_ast_hpma_rd_condit_ratings,
    #     "NUM;HWY_ID;BEGIN_DESC;END_DESC;BEGIN_REFP;END_REFP;DISTRICT;FUNC_CLASS;ADMIN_SYS;LANES;LENGTH;WIDTH;PAVETYPE;PCI_YEAR;ADDBY;MODBY;ADDDATE;MODDATE;SDATE;SOURCE;SACC;PCI_MRM",
    #     "DELETE_FIELDS"
    # )
    #
    # arcpy.SpatialJoin_analysis(
    #     local_ast_hpma_rd_condit_ratings,
    #     second_midpoints_sjoin,
    #     r"T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature",
    #     "JOIN_ONE_TO_ONE",
    #     "KEEP_COMMON",
    #     'Join_Count "Join_Count" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,Join_Count,-1,-1;TARGET_FID "TARGET_FID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,TARGET_FID,-1,-1;ORIG_FID "ORIG_FID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,ORIG_FID,-1,-1;NUM "Route Number" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,NUM,-1,-1;HWY_ID "Street Name" true true false 32 Text 0 0,First,#,second_midpoints_sjoin,HWY_ID,0,32;BEGIN_DESC "From Street" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,BEGIN_DESC,0,50;END_DESC "To Street" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,END_DESC,0,50;BEGIN_REFP "Start Km Limit of section" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,BEGIN_REFP,-1,-1;END_REFP "End KM Limit of section" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,END_REFP,-1,-1;DISTRICT "District" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,DISTRICT,-1,-1;FUNC_CLASS "Street Class" true true false 3 Text 0 0,First,#,second_midpoints_sjoin,FUNC_CLASS,0,3;ADMIN_SYS "Owner" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,OWN_1,0,4;LANES "Number of Lanes" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,LANECOUNT_1,-1,-1;LENGTH "Length" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,LENGTH,-1,-1;WIDTH "Width" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,WIDTH,-1,-1;PAVETYPE "Material" true true false 3 Text 0 0,First,#,second_midpoints_sjoin,PAVETYPE,0,3;PCI_YEAR "PQI Rating Year" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,PCI_YEAR,-1,-1;SDATE "Source Date" true true false 8 Date 0 0,First,#,second_midpoints_sjoin,SDATE,-1,-1;SACC "Source Accuracy" true true false 2 Text 0 0,First,#,second_midpoints_sjoin,SACC,0,2;PCI_MRM "PQI Rating" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,PCI_MRM,-1,-1;TEMP_ID "TEMP_ID" true true false 2 Short 0 0,First,#,second_midpoints_sjoin,TEMP_ID,-1,-1;Join_Count_1 "Join_Count" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,Join_Count_1,-1,-1;TARGET_FID_1 "TARGET_FID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,TARGET_FID_1,-1,-1;ROUTENUM "ROUTENUM" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,ROUTENUM,-1,-1;BEGIN_MILE "BEGIN_MILE" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,BEGIN_MILE,-1,-1;END_MILE "END_MILE" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,END_MILE,-1,-1;PQI_MRM "PQI_MRM" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,PQI_MRM,-1,-1;CONDITION "CONDITION" true true false 16 Text 0 0,First,#,second_midpoints_sjoin,CONDITION,0,16;OWN "OWN" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,OWN,0,4;LANECOUNT "Lane Count" true true false 2 Short 0 0,First,#,second_midpoints_sjoin,LANECOUNT,-1,-1;FCODE "FCODE" true true false 12 Text 0 0,First,#,second_midpoints_sjoin,FCODE,0,12;STR_NAME "STR_NAME" true true false 40 Text 0 0,First,#,second_midpoints_sjoin,STR_NAME,0,40;STR_TYPE "STR_TYPE" true true false 6 Text 0 0,First,#,second_midpoints_sjoin,STR_TYPE,0,6;FULL_NAME "FULL_NAME" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,FULL_NAME,0,50;MUN_CODE "MUN_CODE" true true false 3 Text 0 0,First,#,second_midpoints_sjoin,MUN_CODE,0,3;FROM_STR "FROM_STR" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,FROM_STR,0,50;TO_STR "TO_STR" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,TO_STR,0,50;STR_DIR "STR_DIR" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,STR_DIR,0,4;STR_STATUS "STR_STATUS" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,STR_STATUS,0,4;ST_CLASS "ST_CLASS" true true false 40 Text 0 0,First,#,second_midpoints_sjoin,ST_CLASS,0,40;OWN_1 "OWN" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,OWN_1,0,4;MAINTENANCE "Winter Maintenance" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,MAINTENANCE,0,4;DATE_ACCEPT "DATE_ACCEPT" true true false 8 Date 0 0,First,#,second_midpoints_sjoin,DATE_ACCEPT,-1,-1;FROM_ELEV "FROM_ELEV" true true false 2 Short 0 0,First,#,second_midpoints_sjoin,FROM_ELEV,-1,-1;TO_ELEV "TO_ELEV" true true false 2 Short 0 0,First,#,second_midpoints_sjoin,TO_ELEV,-1,-1;STR_REM "STR_REM" true true false 100 Text 0 0,First,#,second_midpoints_sjoin,STR_REM,0,100;PSAB_CODE "PSAB_CODE" true true false 12 Text 0 0,First,#,second_midpoints_sjoin,PSAB_CODE,0,12;FLAGS "FLAGS" true true false 35 Text 0 0,First,#,second_midpoints_sjoin,FLAGS,0,35;ACC "ACC" true true false 5 Text 0 0,First,#,second_midpoints_sjoin,ACC,0,5;DATE_ACT "DATE_ACT" true true false 8 Date 0 0,First,#,second_midpoints_sjoin,DATE_ACT,-1,-1;SYS_DATE "SYS_DATE" true true false 8 Date 0 0,First,#,second_midpoints_sjoin,SYS_DATE,-1,-1;FDMID "FDMID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,FDMID,-1,-1;ROUTE_ID "ROUTE_ID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,ROUTE_ID,-1,-1;FROM_LEFT "FROM_LEFT" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,FROM_LEFT,-1,-1;TO_LEFT "TO_LEFT" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,TO_LEFT,-1,-1;FROM_RIGHT "FROM_RIGHT" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,FROM_RIGHT,-1,-1;TO_RIGHT "TO_RIGHT" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,TO_RIGHT,-1,-1;OLD_FDMID "OLD_FDMID" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,OLD_FDMID,-1,-1;GSA_LEFT "Left Community" true true false 40 Text 0 0,First,#,second_midpoints_sjoin,GSA_LEFT,0,40;GSA_RIGHT "Right Community" true true false 40 Text 0 0,First,#,second_midpoints_sjoin,GSA_RIGHT,0,40;PAR_LEFT "Left Parity" true true false 10 Text 0 0,First,#,second_midpoints_sjoin,PAR_LEFT,0,10;PAR_RIGHT "Right Parity" true true false 10 Text 0 0,First,#,second_midpoints_sjoin,PAR_RIGHT,0,10;STR_CODE_L "Left Street Code" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,STR_CODE_L,-1,-1;STR_CODE_R "Right Street Code" true true false 4 Long 0 0,First,#,second_midpoints_sjoin,STR_CODE_R,-1,-1;ASSETID "Asset ID" true true false 50 Text 0 0,First,#,second_midpoints_sjoin,ASSETID,0,50;MAINTSUMMER "Summer Maintenance" true true false 4 Text 0 0,First,#,second_midpoints_sjoin,MAINTSUMMER,0,4;LANECOUNT_1 "Lane Count" true true false 2 Short 0 0,First,#,second_midpoints_sjoin,LANECOUNT_1,-1,-1;TECH_MOD "Modified by" true true false 32 Text 0 0,First,#,second_midpoints_sjoin,TECH_MOD,0,32;TECH_ACT "Added by" true true false 32 Text 0 0,First,#,second_midpoints_sjoin,TECH_ACT,0,32;Shape_Length_1 "Shape_Length" true true false 8 Double 0 0,First,#,second_midpoints_sjoin,Shape_Length_1,-1,-1',
    #     "INTERSECT",
    #     None,
    #     '')

    # TODO: Check results - year (2022)
    # Calculate final feature year as 2022..
    # arcpy.management.CalculateField("final_feature", "PCI_YEAR", "2022", "PYTHON3", '', "TEXT", "NO_ENFORCE_DOMAINS")

    # TODO: Append to SDE
    # arcpy.Append_management(
    #     "final_feature",
    #     "GISRW01.SDEADM.AST_hpma_rd_condit_rating",
    #     "NO_TEST",
    #     r'NUM "Route Number" true true false 4 Long 0 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,NUM,-1,-1;HWY_ID "Street Name" true true false 32 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,HWY_ID,0,32;BEGIN_DESC "From Street" true true false 50 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,BEGIN_DESC,0,50;END_DESC "To Street" true true false 50 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,END_DESC,0,50;BEGIN_REFP "Start Km Limit of section" true true false 8 Double 5 15,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,BEGIN_REFP,-1,-1;END_REFP "End KM Limit of section" true true false 8 Double 5 15,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,END_REFP,-1,-1;DISTRICT "District" true true false 4 Long 0 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,DISTRICT,-1,-1;FUNC_CLASS "Street Class" true true false 3 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,FUNC_CLASS,0,3;ADMIN_SYS "Owner" true true false 4 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,ADMIN_SYS,0,4;LANES "Number of Lanes" true true false 4 Long 0 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,LANES,-1,-1;LENGTH "Length" true true false 8 Double 5 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,LENGTH,-1,-1;WIDTH "Width" true true false 8 Double 5 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,WIDTH,-1,-1;PAVETYPE "Material" true true false 3 Text 0 0,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,PAVETYPE,0,3;PCI_YEAR "PQI Rating Year" true true false 4 Long 0 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,PCI_YEAR,-1,-1;SDATE "Source Date" true true false 8 Date 0 0,First,#;SOURCE "Data Source" true true false 20 Text 0 0,First,#;SACC "Source Accuracy" true true false 2 Text 0 0,First,#;GLOBALID "GLOBALID" false false true 38 GlobalID 0 0,First,#;PCI_MRM "PQI Rating" true true false 8 Double 2 10,First,#,T:\work\giss\monthly\202312dec\gallaga\pavement_condition_data\scratch_REWRITE.gdb\final_feature,PCI_MRM,-1,-1',
    # )
    #
    # # Calculate fields
    # arcpy.management.CalculateField("GISRW01.SDEADM.AST_hpma_rd_condit_rating", "SDATE", "!ADDDATE!", "PYTHON3", '',
    #                                 "TEXT", "NO_ENFORCE_DOMAINS")
    #
    # arcpy.management.CalculateField("GISRW01.SDEADM.AST_hpma_rd_condit_rating", "SOURCE", "'TPW'", "PYTHON3", '',
    #                                 "TEXT", "NO_ENFORCE_DOMAINS")
    #
    # arcpy.management.CalculateField("GISRW01.SDEADM.AST_hpma_rd_condit_rating", "SACC", "'IN'", "PYTHON3", '', "TEXT",
    #                                 "NO_ENFORCE_DOMAINS")

    # Append to RO. Select records with 2022 date in RW
    # arcpy.management.Append("GISRW01.SDEADM.AST_hpma_rd_condit_rating",
    #                         r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RO_sdeadm.sde\GISRO01.SDEADM.AST_hpma_rd_condit_rating",
    #                         "NO_TEST",
    #                         r'NUM "Route Number" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,NUM,-1,-1;HWY_ID "Street Name" true true false 32 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,HWY_ID,0,32;BEGIN_DESC "From Street" true true false 50 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,BEGIN_DESC,0,50;END_DESC "To Street" true true false 50 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,END_DESC,0,50;BEGIN_REFP "Start Km Limit of section" true true false 8 Double 5 15,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,BEGIN_REFP,-1,-1;END_REFP "End KM Limit of section" true true false 8 Double 5 15,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,END_REFP,-1,-1;DISTRICT "District" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,DISTRICT,-1,-1;FUNC_CLASS "Street Class" true true false 3 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,FUNC_CLASS,0,3;ADMIN_SYS "Owner" true true false 4 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,ADMIN_SYS,0,4;LANES "Number of Lanes" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,LANES,-1,-1;LENGTH "Length" true true false 8 Double 5 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,LENGTH,-1,-1;WIDTH "Width" true true false 8 Double 5 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,WIDTH,-1,-1;PAVETYPE "Material" true true false 3 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,PAVETYPE,0,3;PCI_YEAR "PQI Rating Year" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,PCI_YEAR,-1,-1;ADDBY "Add by" true true false 32 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,ADDBY,0,32;MODBY "Modified by" true true false 32 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,MODBY,0,32;ADDDATE "Add Date" true true false 8 Date 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,ADDDATE,-1,-1;MODDATE "Modified Date" true true false 8 Date 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,MODDATE,-1,-1;SDATE "Source Date" true true false 8 Date 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,SDATE,-1,-1;SOURCE "Data Source" true true false 20 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,SOURCE,0,20;SACC "Source Accuracy" true true false 2 Text 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,SACC,0,2;GLOBALID "GLOBALID" false false true 38 GlobalID 0 0,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,GLOBALID,-1,-1;PCI_MRM "PQI Rating" true true false 8 Double 2 10,First,#,E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde\GISRW01.SDEADM.AST_hpma_rd_condit_rating,PCI_MRM,-1,-1',
    #                         '', '')


if __name__ == "__main__":

    startTime = time.asctime(time.localtime(time.time()))
    logger.info("Start: " + startTime)
    logger.info("-----------------------")

    new_hpma_data = os.path.join(os.getcwd(), "sauce", "HRM 2022 PQI.shp")

    GDB_NAME = "scratch_REWRITE_AUG_II.gdb"

    try:
        local_gdb = utils.create_fgdb(os.getcwd(), GDB_NAME)

        # Prepare data
        local_trn_streets, local_hpma, local_sde_ast_hpma = setup_workspace(local_gdb, SDE, new_hpma_data)
        filtered_trn_streets = filter_streets(local_trn_streets, local_gdb)

        # Analyze
        hrm_streets_w_hpma = analyze_features(filtered_trn_streets, local_hpma, local_gdb, local_sde_ast_hpma)

        # arcpy.management.TruncateTable(
        #     in_table="GISRO01.SDEADM.TRN_Street_HPMA_Ratings"
        # )
        #
        # arcpy.management.Append(
        #     inputs="trn_street_midpoints_w_hpma",
        #     target="GISRO01.SDEADM.TRN_Street_HPMA_Ratings",
        #     schema_type="NO_TEST",
        #     # TODO: Make sure PCI field matches
        #     field_mapping=r'FULL_NAME "FULL_NAME" true true false 50 Text 0 0,First,#,T:\work\giss\monthly\202408aug\gallaga\pavement_condition_data\scratch_REWRITE_AUG_II.gdb\trn_street_midpoints_w_hpma,FULL_NAME,0,49;FDMID "FDMID" true true false 4 Long 0 0,First,#,T:\work\giss\monthly\202408aug\gallaga\pavement_condition_data\scratch_REWRITE_AUG_II.gdb\trn_street_midpoints_w_hpma,FDMID,-1,-1;HWY_ID "Street Name" true true false 32 Text 0 0,First,#,T:\work\giss\monthly\202408aug\gallaga\pavement_condition_data\scratch_REWRITE_AUG_II.gdb\trn_street_midpoints_w_hpma,HWY_ID,0,31;PCI_MRM "PCI Rating" true true false 8 Double 0 0,First,#,trn_street_midpoints_w_hpma,PQI_MRM,-1,-1',
        #     subtype="",
        #     expression="",
        #     match_fields=None,
        #     update_geometry="NOT_UPDATE_GEOMETRY"
        # )
        '''
            Alias Changes:
            
            HWY_ID: Alias updated to "Street Name".
            PCI_MRM: Alias updated to "PCI Rating".
            Substring Ranges:
            
            FULL_NAME: Substring applied from positions 0 to 49.
            HWY_ID: Substring applied from positions 0 to 31.
            Source Field Change:
            
            PCI_MRM: Mapped from PQI_MRM (not directly from a field named PCI_MRM).
            No Substring Applied:
            
            For FDMID and PCI_MRM, the substring start and end positions are set to -1, meaning the entire field value is used.
        '''

    except arcpy.ExecuteError:
        arcpy_msg = arcpy.GetMessages(2)
        print(arcpy_msg)
        logger.error(arcpy_msg)

    except Exception as e:
        print(e)

        # Return any python specific errors as well as any errors from the geoprocessor
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]
        pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
                str(sys.exc_info()[0]) + ": " + str(sys.exc_info()[1]) + "\n"
        logger.error(pymsg)

        msgs = "GP ERRORS:\n" + arcpy.GetMessages(2) + "\n"
        logger.error(msgs)

        # send_error("ERROR - BUILDING PERMIT ERROR", "DC1-GIS-APP-Q203 / BuildingPermits.py")

        sys.exit()

    # Close the Log File:
    endTime = time.asctime(time.localtime(time.time()))
    logger.info("-----------------------")
    logger.info("End: " + endTime)
