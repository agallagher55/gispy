import os
import arcpy
import logging

import sql_cmds

import pandas as pd

from datetime import datetime
from configparser import ConfigParser

from metadata import (
    get_sde_metadata,
    update_metadata,
)

# from HRMutils import send_mail

config = ConfigParser()
config.read("../config.ini")

# Logging
log_dir = os.getcwd()

# File handler
log_file = os.path.join(log_dir, "script_logs.log")
file_handler = logging.FileHandler(log_file)

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
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)  # Write logs to a file
logger.addHandler(console_handler)  # logger.info logs to the console

SDE_RW = config.get("GIS_DATA", "SDE_RW")
SDE_RO = config.get("GIS_DATA", "SDE_RO")

PARCEL_LOAD_DIR = config.get("GIS_DATA", "PARCEL_LOAD_DIR")

PARCEL_POINT_RW = config.get("GIS_DATA", "PARCEL_POINT_RW")
PARCEL_POINT_SINGLE_RW = config.get("GIS_DATA", "PARCEL_POINT_SINGLE_RW")
PARCEL_POINT_OLD_SDE_RW = config.get("GIS_DATA", "PARCEL_POINT_OLD_SDE_RW")

LINNS_PIDMSTRS_SDE_RW = config.get("GIS_DATA", "LINNS_PIDMSTRS_SDE_RW")
LINNS_ALL_SDE_RW = config.get("GIS_DATA", "LINNS_ALL_SDE_RW")
LINNS_ALL_STAGE_RW = config.get("GIS_DATA", "LINNS_ALL_STAGE_RW")

LINNS_PIDMSTRS_SDE_RO = config.get("GIS_DATA", "LINNS_PIDMSTRS_SDE_RO")
LINNS_ALL_SDE_RO = config.get("GIS_DATA", "LINNS_ALL_SDE_RO")

LND_GHOSTED_PARCEL_LINE_RW = config.get("GIS_DATA", "LND_GHOSTED_PARCEL_LINE_RW")
LND_PARCEL_LINE_RW = config.get("GIS_DATA", "LND_PARCEL_LINE_RW")
LND_PARCEL_POLYGON_RW = config.get("GIS_DATA", "LND_PARCEL_POLYGON_RW")

PIDMSTRS_DBF = config.get("GIS_DATA", "PIDMSTRS_DBF")

CURRENT_MONTH = datetime.now().strftime('%B')  # Date format YYMMDD

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)


def parcel_poly_to_point(parcel_poly_reference_feature, fgdb, repair_geometry=False):

    logging.info("Running parcel_poly_to_point...")

    feature_to_point_fc = os.path.join(fgdb, f"hrm_parcel_polygon_points")
    point_multi_feature = os.path.join(fgdb, f"hrm_parcel_polygon_points_multi")

    if repair_geometry:

        logger.info("Repair Geometry...")
        arcpy.RepairGeometry_management(
            in_features=parcel_poly_reference_feature,
            delete_null="KEEP_NULL",
            validation_method="ESRI"
        )
        logger.debug(arcpy.GetMessages())

    logger.info("Feature To Point...")
    arcpy.FeatureToPoint_management(
        in_features=parcel_poly_reference_feature,
        out_feature_class=feature_to_point_fc,
        point_location="INSIDE"
    )
    logger.debug(arcpy.GetMessages())

    logger.info("Pairwise Dissolve...")
    arcpy.PairwiseDissolve_analysis(
        in_features=feature_to_point_fc,
        out_feature_class=point_multi_feature,
        dissolve_field=["PID"],
        multi_part="MULTI_PART"
    )
    logger.debug(arcpy.GetMessages())

    return feature_to_point_fc, point_multi_feature


def update_parcel_pt(rw_workspace, local_gdb):

    logging_separator = "=" * 50

    lnd_parcel_poly = os.path.join(rw_workspace, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

    lnd_parcel_point_multi_sde_rw = os.path.join(rw_workspace, "SDEADM.LND_parcel_point")
    lnd_parcel_point_single_sde_rw = os.path.join(rw_workspace, "SDEADM.LND_parcel_point_single")

    # Parcel Polygon to point feature, dissolve on PID

    local_parcel_pt_single, local_parcel_pt_multi = parcel_poly_to_point(lnd_parcel_poly, local_gdb)

    logger.info(logging_separator)

    # Delete rows in RW feature
    for sde_feature in lnd_parcel_point_multi_sde_rw, lnd_parcel_point_single_sde_rw:
        logger.info(f"Truncating {sde_feature}...")
        arcpy.TruncateTable_management(sde_feature)
        logger.debug(arcpy.GetMessages())

    logger.info(logging_separator)

    # Multi feature
    logging.info(f"Loading {lnd_parcel_point_multi_sde_rw}...")
    arcpy.Append_management(
        inputs=local_parcel_pt_multi,
        target=lnd_parcel_point_multi_sde_rw,
        schema_type="NO_TEST",
    )
    logger.debug(arcpy.GetMessages())


def backup_and_trunc_parcel_point(workspace: str = r"C:\Workspace\Parcel_Load\Scratch") -> str:
    """
    Backup the LND_parcel_point feature class in SDE RW as a shapefile in the specified workspace.
    If the backup contains rows, truncate the LND_PARCEL_POINT_OLD feature class in SDE RW.

    :param workspace: The path to the workspace where the backup shapefile will be saved.

    Returns: The path to the backup shapefile.

    Raises:
        ValueError: If the backup shapefile contains no rows.
    """

    parcel_point_backup = os.path.join(workspace, "LND_PARCEL_POINT.shp")

    logger.info(f"Backing up {PARCEL_POINT_RW}...")
    arcpy.FeatureClassToShapefile_conversion(
        Input_Features=PARCEL_POINT_RW,
        Output_Folder=workspace,
    )
    logger.info(arcpy.GetMessages())

    # Make sure backup has rows
    row_count = int(arcpy.GetCount_management(parcel_point_backup)[0])
    logger.info(f"Row count in {parcel_point_backup}: {row_count}")

    if row_count > 0:
        # Truncate the feature class LND_PARCEL_POINT_OLD in SDE RW.
        logger.info(f"\tTruncating {PARCEL_POINT_OLD_SDE_RW}...")
        arcpy.TruncateTable_management(in_table=PARCEL_POINT_OLD_SDE_RW)

    else:
        raise ValueError(f"Did not find any records in the backup. Check backup was made successfully and run again.")

    return parcel_point_backup


def truncate_load_linns(sde_rw=SDE_RW, sde_ro=SDE_RO, dbf_workspace=PARCEL_LOAD_DIR):
    """
    Truncate and load LINNS data from SDE and dbf files
    This function loads LINNS data from SDE and dbf files and truncates the existing data in the LINNS tables.
    ~Should take about 5 to 10 minutes to run.

    :param sde_rw: the file path to the read-write SDE file
    :param sde_ro: the file path to the read-only SDE file
    :param dbf_workspace: the file path to the dbf workspace
    :return:
    """

    logger.info("Truncating & Loading LINNS tables...")

    dbf_linns_pidaantax = os.path.join(dbf_workspace, "pidaantax.dbf")
    dbf_linns_pidnames = os.path.join(dbf_workspace, "pidnames.dbf")
    dbf_linns_pidrelate = os.path.join(dbf_workspace, "pidrelate.dbf")
    dbf_linns_pidaddress = os.path.join(dbf_workspace, "pidaddress.dbf")
    dbf_linns_piddocs = os.path.join(dbf_workspace, "piddocs.dbf")
    dbf_linns_pidplans = os.path.join(dbf_workspace, "pidplans.dbf")
    dbf_linns_pidretire = os.path.join(dbf_workspace, "pidretire.dbf")

    sde_linns_pidaantax = os.path.join(sde_rw, "SDEADM.LINNS_PIDAANTAX")
    sde_linns_pidnames = os.path.join(sde_rw, "SDEADM.LINNS_PIDNAMES")
    sde_linns_pidrelate = os.path.join(sde_rw, "SDEADM.LINNS_PIDRELATE")
    sde_linns_pidmstrs = os.path.join(sde_rw, "SDEADM.LINNS_PIDMSTRS")

    rosde_linns_pidaantax = os.path.join(sde_ro, "SDEADM.LINNS_PIDAANTAX")
    rosde_linns_pidnames = os.path.join(sde_ro, "SDEADM.LINNS_PIDNAMES")
    rosde_linns_pidrelate = os.path.join(sde_ro, "SDEADM.LINNS_PIDRELATE")
    rosde_linns_pidaddress = os.path.join(sde_ro, "SDEADM.LINNS_PIDADDRESS")
    rosde_linns_piddocs = os.path.join(sde_ro, "SDEADM.LINNS_PIDDOCS")
    rosde_linns_pidplans = os.path.join(sde_ro, "SDEADM.LINNS_PIDPLANS")
    rosde_linns_pidretire = os.path.join(sde_ro, "SDEADM.LINNS_PIDRETIRE")
    rosde_linns_pidmstrs = os.path.join(sde_ro, "SDEADM.LINNS_PIDMSTRS")

    for features in [
        (sde_linns_pidaantax, dbf_linns_pidaantax),
        (sde_linns_pidnames, dbf_linns_pidnames),
        (sde_linns_pidrelate, dbf_linns_pidrelate),
        (sde_linns_pidmstrs, None),

        (rosde_linns_pidaantax, dbf_linns_pidaantax),
        (rosde_linns_pidnames, dbf_linns_pidnames),
        (rosde_linns_pidrelate, dbf_linns_pidrelate),
        (rosde_linns_pidaddress, dbf_linns_pidaddress),
        (rosde_linns_piddocs, dbf_linns_piddocs),
        (rosde_linns_pidplans, dbf_linns_pidplans),
        (rosde_linns_pidretire, dbf_linns_pidretire),
        (rosde_linns_pidmstrs, None),
    ]:
        sde_feature, dbf_feature = features[0], features[1]
        arcpy.AddMessage(f'Truncating {sde_feature}...')
        arcpy.TruncateTable_management(sde_feature)

        if dbf_feature:
            arcpy.AddMessage(f'\tAppending {dbf_feature} to {sde_feature}...')
            arcpy.Append_management(dbf_feature, sde_feature, "NO_TEST", "", "")

        else:
            logger.info(f"\t**Need to append to {sde_feature} MANUALLY...")
            # load_linns_pidmstrs(PIDMSTRS_DBF, sde_linns_pidmstrs)

            # feature class into the RW database with the data in the pidmstrs.dbf table from the province.


def load_linns_pidmstrs(dbf_pidmstrs: str, sde_pidmstrs: str):
    """
    Load data from local LINNS_pidmstrs table into SDE LINNS_pidmstrs table

    This function loads data from a local LINNS_pidmstrs table into a SDE LINNS_pidmstrs table by first converting the
    local table to a Pandas dataframe, then to a list of tuples.
    The function then truncates the existing data in the LINNS SDE table and inserts the data from the local LINNS table.

    Parameters:
    dbf_linns (str): the file path to the local LINNS table - pidmstrs.dbf
    sde_linns (str): the file path to the LINNS SDE table

    """

    # TODO: add to truncate_load_linns() ?

    logger.info(f"Loading SDE LINNS table with dbf pidmstrs table, {dbf_pidmstrs}...")

    linns_area_field = 'SDEADM.LINNS_PIDMSTRS.AREA'

    # Feature to dataframe, dataframe to dictionary
    fields = [x.name for x in arcpy.ListFields(dbf_pidmstrs) if x.name not in ("OID", "PIDS")]

    # TODO: Use search cursor here instead
    local_linns_df = pd.DataFrame([row for row in arcpy.da.SearchCursor(dbf_pidmstrs, fields)], columns=fields)
    local_linns_records = [tuple(row) for row in local_linns_df.to_numpy().tolist()]

    # Make sure LINNS SDE table has no records
    linns_sde_row_count = int(arcpy.GetCount_management(sde_pidmstrs)[0])

    if linns_sde_row_count == 0:
        logger.info(f"LINNS SDE table has been truncated")

        # Insert records from LINNS dbf table into SDE table
        linns_local_row_count = len(local_linns_records)
        logger.info(f"Inserting {linns_local_row_count} records into LINNS SDE table...")

        linns_sde_fields = [
            "PID", "PID_STATUS", "LANDTITLE", "LANDRELATE", "PARCELTYPE", "CONDO_CORP", "OWNER_STAT",
            "AREA_UNIT", linns_area_field, "AREA_CERT", "AREA_HECT", "STARTDATE"
        ]

        # Load LINNS sde table from dbf file
        with arcpy.da.InsertCursor(sde_pidmstrs, linns_sde_fields) as cursor:
            for row in local_linns_records:
                cursor.insertRow(row)

        del cursor

    else:
        raise ValueError(f"ERROR: {sde_pidmstrs} needs to be truncated before it can be loaded!")

    # Ensure all AREA values are present
    sde_linns_area = [row[0] for row in arcpy.da.SearchCursor(sde_pidmstrs, linns_area_field)]

    # Fields should be set to Null - LANDREL_CD, UPD_Date

    logger.info("Check to make sure area field values are not null")

    num_area_null = len([x for x in sde_linns_area if not x])  # This raised an error when it shouldn't have...?
    if all([x == 0.0 for x in sde_linns_area]) > 0:
        raise ValueError(f"Check {sde_pidmstrs} to ensure area field values transferred over.")


def truncate_load_rw(shp_parcel_point):
    """
    STEP 3 in documentation
    ~ 15 to 20 minutes to run

    Truncate RW_LND_parcel_point_old

    TRUNCATE RW_LND_parcel_point_single     and LOAD     SHP_clipped_parcel_labels
    TRUNCATE RW_LND_parcel_point            and LOAD     SHP_Dissolved_parcel_point
    TRUNCATE RW_LND_ghosted_parcel_line     and LOAD     SHP_Select_Ghosted_Line
    TRUNCATE RW_LND_parcel_line             and LOAD     SHP_Select_Parcel_Line
    TRUNCATE RW_LND_parcel_polygon          and LOAD     SHP_Parcel_polygon

    """

    # TODO: Refactor/cleanup

    logger.info("Truncating & loading RW...")

    # These get created in step 1
    shp_select_ghosted_line = os.path.join(PARCEL_LOAD_DIR, "Select_Ghosted_Line.shp")
    shp_select_parcel_line = os.path.join(PARCEL_LOAD_DIR, "Select_Parcel_Line.shp")
    shp_parcel_polygon = os.path.join(PARCEL_LOAD_DIR, "Parcel_Polygon.shp")

    for features in [
        (PARCEL_POINT_OLD_SDE_RW, None),  # Make backup
        (LND_GHOSTED_PARCEL_LINE_RW, shp_select_ghosted_line),
        (LND_PARCEL_LINE_RW, shp_select_parcel_line),
        (LND_PARCEL_POLYGON_RW, shp_parcel_polygon)
    ]:

        sde_feature, load_feature = features[0], features[1]

        logger.info(f"Truncating {sde_feature}...")
        arcpy.TruncateTable_management(sde_feature)

        if sde_feature == PARCEL_POINT_OLD_SDE_RW:
            logger.info(f"\tLoading old parcel point, {shp_parcel_point}, into {PARCEL_POINT_OLD_SDE_RW}...")
            arcpy.Append_management(
                shp_parcel_point,
                PARCEL_POINT_OLD_SDE_RW,
                "TEST",
            )

        else:
            logger.info(f"\tAppending {load_feature} to {sde_feature}...")
            arcpy.Append_management(load_feature, sde_feature, "NO_TEST")


def truncate_load_linns_all_rw():

    logger.info(f"Truncating & loading '{LINNS_ALL_SDE_RW}'...")

    # Make sure backup has rows
    row_count = int(arcpy.GetCount_management(LINNS_ALL_SDE_RW)[0])
    logger.info(f"Current row count of {LINNS_ALL_SDE_RW}: {row_count}")
    if row_count > 0:
        # Truncate the feature class LND_PARCEL_POINT_OLD in SDE RW.
        logger.info(f"\tTruncating {LINNS_ALL_SDE_RW}...")
        arcpy.TruncateTable_management(in_table=LINNS_ALL_SDE_RW)

    else:
        raise ValueError(f"Did not find any records in the backup. Check backup was made successfully and run again.")

    # Append LINNS_ALL_STAGE to LINNS_ALL using the Append tool.
    logger.info(f"Appending {LINNS_ALL_STAGE_RW} into {LINNS_ALL_SDE_RW}...")
    arcpy.Append_management(
        LINNS_ALL_STAGE_RW,
        LINNS_ALL_SDE_RW,
        "NO_TEST",
        r'PID "PID" true true false 8 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,PID,0,8;AAN "AAN" true true false 8 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,AAN,0,8;AREAUNITS "AREAUNITS" true true false 25 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,AREAUNITS,0,25;MAILING "MAILING" true true false 250 Text 0 0,First,#;OWNER1 "OWNER1" true true false 100 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,OWNER1,0,100;OWNER2 "OWNER2" true true false 100 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,OWNER2,0,100;TYPE "TYPE" true true false 10 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,TYPE,0,10;ASSESSMENT "ASSESSMENT" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL_STAGE,ASSESSMENT,-1,-1',
    )

    # TODO: Check that Assessment gets loaded.

    # Notes:
    # - LINNS_ALL_STAGE is not registered with GDB.

    # - Assessment field might be double instead integer. Load tool will not work in this case so use Append tool.
    # - LINNS ALL is a joined table to create the view that ppl use.
    # - When loading LINNS_ALL from stage table, the mailing field has been dropped so it shows up as none.
    # - Check that Assessment gets loaded.


def load_pidmstrs_ro():
    """
    MANUAL STEP: Truncate and load LINNS_PIDMSTR in the RO database.
    1.	Truncate LINNS_PIDMSTR.
    2.	Load LINNS_PIDMSTR from RW database into LINNS_PIDMSTR in RO database.
    """

    logger.info("Loading PIDMSTRS (RO)...")

    row_count = int(arcpy.GetCount_management(LINNS_PIDMSTRS_SDE_RO)[0])
    logger.info(f"RO row count: {row_count}")

    if row_count > 0:
        logger.info(f"Truncating {LINNS_PIDMSTRS_SDE_RO}...")
        arcpy.TruncateTable_management(in_table=LINNS_PIDMSTRS_SDE_RO)

    omit_fields = ["LANDREL_CD", 'UPD_DATE']  # Prov data does not have these fields
    pid_mstrs_fields = [x.name for x in arcpy.ListFields(LINNS_PIDMSTRS_SDE_RW) if x.name not in omit_fields]
    linns_pidmstrs_rw_data = [row for row in arcpy.da.SearchCursor(LINNS_PIDMSTRS_SDE_RW, pid_mstrs_fields)]

    logger.info(f"Appending {LINNS_PIDMSTRS_SDE_RW} into {LINNS_PIDMSTRS_SDE_RO}...")
    pid_mstrs_fields = [
        'GISRO01.SDEADM.LINNS_PIDMSTRS.AREA' if x == 'GISRW01.SDEADM.LINNS_PIDMSTRS.AREA' else x
        for x in pid_mstrs_fields
    ]
    with arcpy.da.InsertCursor(LINNS_PIDMSTRS_SDE_RO, pid_mstrs_fields) as cursor:
        for row in linns_pidmstrs_rw_data:
            cursor.insertRow(row)

    # Make sure Area field in RO gets updated
    area_field = [x for x in pid_mstrs_fields if x.upper().endswith("AREA")][0]
    area_values = [row[0] for row in arcpy.da.SearchCursor(LINNS_PIDMSTRS_SDE_RO, area_field)]
    if all([x == "" for x in area_values]):
        # Truncate LINNS_PIDMSTRS_SDE_RO and re-load/append
        raise ValueError(f"It looks like the area field in {LINNS_PIDMSTRS_SDE_RO} did not get updated!")


def load_linns_all():
    """
    MANUAL STEP: Truncate and load LINNS_ALL in the RO database.
    1.	Truncate LINNS_ALL.
    2.	Load LINNS_ALL from RW database into LINNS_ALL in RO database.
    """

    logger.info("Loading LINNS_ALL (RO)...")

    row_count = int(arcpy.GetCount_management(LINNS_ALL_SDE_RO)[0])
    logger.info(f"RO row count: {row_count}")

    # Make sure backup has rows
    if row_count > 0:
        # Truncate the feature class LND_PARCEL_POINT_OLD in SDE RW.
        logger.info(f"Truncating {LINNS_ALL_SDE_RO}...")
        arcpy.TruncateTable_management(in_table=LINNS_ALL_SDE_RO)

    else:
        raise ValueError(f"Did not find any records in the backup. Check backup was made successfully and run again.")

    logger.info(f"Appending {LINNS_ALL_SDE_RW} into {LINNS_ALL_SDE_RO}...")
    arcpy.Append_management(
        LINNS_ALL_SDE_RW,
        LINNS_ALL_SDE_RO,
        "NO_TEST",
        r'PID "PID" true true false 8 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,PID,0,8;AAN "AAN" true true false 8 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,AAN,0,8;ASSESSMENT "ASSESSMENT" true true false 4 Long 0 10,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,ASSESSMENT,-1,-1;AREAUNITS "AREAUNITS" true true false 25 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,AREAUNITS,0,25;MAILING "MAILING" true true false 250 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,MAILING,0,250;OWNER1 "OWNER1" true true false 100 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,OWNER1,0,100;OWNER2 "OWNER2" true true false 100 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,OWNER2,0,100;TYPE "TYPE" true true false 10 Text 0 0,First,#,E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde\SDEADM.LINNS_ALL,TYPE,0,10'
    )


def trunc_load_spatial_ro_data_from_rw(sde_ro, sde_rw):
    """
    Truncates and appends features from the source to the target geodatabase.
        Features: LND_parcel_point_single, LND_parcel_point, LND_parcel_line, LND_parcel_polygon
    :param sde_ro:
    :param sde_rw:
    :return: 
    """

    logger.info("Truncating & loading RO...")

    if sde_rw == '#' or not sde_rw:
        sde_rw = r"T:\work\giss\tools\Parcel Load\sdeadm_Prod_GIS_Halifax.sde"

    if sde_ro == '#' or not sde_ro:
        sde_ro = r"T:\work\giss\tools\Parcel Load\sdeadm_Prod_GIS_ReadOnly.sde"

    feature_pairs = [
        (
            os.path.join(sde_rw, "SDEADM.LND_parcel_point_single"),
            os.path.join(sde_ro, "SDEADM.LND_parcel_point_single")
        ),
        (
            os.path.join(sde_rw, "SDEADM.LND_parcel_point"),
            os.path.join(sde_ro, "SDEADM.LND_parcel_point")
        ),
        (
            os.path.join(sde_rw, "SDEADM.LND_parcels", "SDEADM.LND_parcel_line"),
            os.path.join(sde_ro, "SDEADM.LND_parcels", "SDEADM.LND_parcel_line")
        ),
        (
            os.path.join(sde_rw, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon"),
            os.path.join(sde_ro, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")
        )
    ]

    try:
        for source_feature, target_feature in feature_pairs:
            arcpy.AddMessage(f"Truncating {target_feature} ...")
            arcpy.TruncateTable_management(target_feature)

            arcpy.AddMessage(f"\tAppending {source_feature} to {target_feature} ...")
            arcpy.Append_management(source_feature, target_feature, "NO_TEST", "", "")

    except arcpy.ExecuteError:
        msgs = "GP ERRORS:" + arcpy.GetMessages(2) + ""
        arcpy.AddMessage(msgs)


if __name__ == "__main__":

    # TODO: Add logging

    from datetime import datetime

    logger.info(f"{datetime.now()}")

    backup_gdb = os.path.join(PARCEL_LOAD_DIR, f"{CURRENT_MONTH}ParcelBackup.gdb")
    # TODO: Create workspace gdb (for LND_parcel_point)

    # Back up LND_PARCEL_POINT
    # parcel_pt_backup = os.path.join(PARCEL_LOAD_DIR, "LND_PARCEL_POINT.shp")
    parcel_pt_backup = backup_and_trunc_parcel_point(PARCEL_LOAD_DIR)

    # Step 2: Truncate LINNS Tables tool. ~5 to 10 minutes to run
    truncate_load_linns(SDE_RW, SDE_RO, PARCEL_LOAD_DIR)

    # Step 2B: Load LINNS tables - Manual Step (in docs)
    load_linns_pidmstrs(PIDMSTRS_DBF, LINNS_PIDMSTRS_SDE_RW)

    # Step 3: Truncate and load spatial data in RW. ~15 to 20 minutes to run
    truncate_load_rw(parcel_pt_backup)

    update_parcel_pt(SDE_RW, backup_gdb)

    logger.info(f"{datetime.now()}Running SQL scripts...")

    # new_pidreport_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\create_newpid_report.sql"  # @create_newpid_report.sql
    # update_parcel_line_fcode_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_parcel_line_fcode.sql"
    # update_parcel_poly_fcode_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_parcel_poly_fcode.sql"
    # update_linnstemp_batch_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_linnstemp_batch.sql"

    new_pidreport_sql = r"../sqls/create_newpid_report.sql"  # @create_newpid_report.sql  # TODO: more recently modified - confirm this is the one to use

    update_parcel_line_fcode_sql = r"../sqls/update_parcel_line_fcode.sql"
    update_parcel_poly_fcode_sql = r"../sqls/update_parcel_poly_fcode.sql"
    update_linnstemp_batch_sql = r"../sqls/update_linnstemp_batch.sql"

    new_pids = sql_cmds.execute_sql(new_pidreport_sql, SDE_RW)
    logger.info(f"New PIDs found: {', '.join([x[0] for x in new_pids])}")

    new_pid_report = sql_cmds.pid_report(
        pids=new_pids,
        out_file=r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\newparcels1.lst"
    )
    os.startfile(r"T:\work\giss\tools\Parcel Load\Parcel Load sqls")

    # TODO: Create script to review lst, send email if error

    # TODO: Send email - setup email function
    recipients = [
        # 'gerriom@halifax.ca',
        # 'chapmas@Halifax.ca',
        # 'shijum@halifaxwater.ca',
        # 'caversj@halifax.ca',
        # 'ke59119@halifax.ca',
        # 'craign@halifax.ca',
        # 'so36497@halifax.ca',
        'gallaga@halifax.ca'
    ]
#     send_mail(
#         to=recipients,
#         subject="New Parcels",
#         text="""
# Hi All,
#
# Attached is the new Parcels list.
#
# Take care,
# Alex Gallagher
#         """,
#         # cc="potterm@halifax.ca",
#         # sender=config.get('EMAIL', 'sender'),
#         files=[new_pid_report,],
#         # server=config.get('EMAIL', 'server')
#     )

    sql_cmds.execute_sql(update_parcel_line_fcode_sql, SDE_RW)
    sql_cmds.execute_sql(update_parcel_poly_fcode_sql, SDE_RW)

    sql_cmds.execute_sql(update_linnstemp_batch_sql, SDE_RW)

    # 6. Truncate and Append LINNS_ALL in RW database.
    truncate_load_linns_all_rw()

    # Run Step 4 Script Tool: Truncate & Load Spatial RO Data
    trunc_load_spatial_ro_data_from_rw(SDE_RO, SDE_RW)

    load_pidmstrs_ro()

    load_linns_all()

    # Update Metadata
    logger.info("Updating Metadata...")

    DATE_TODAY = datetime.today().strftime('%Y-%m-%dT00:00:00')

    update_attributes = {
        "revised_date": DATE_TODAY
    }

    rw_features = [
        LND_PARCEL_POLYGON_RW,
        LND_PARCEL_LINE_RW,
        LINNS_ALL_SDE_RW,
        LINNS_PIDMSTRS_SDE_RW,
        LND_GHOSTED_PARCEL_LINE_RW,
        PARCEL_POINT_RW,
        os.path.join(SDE_RW, "SDEADM.LINNS_PIDAANTAX"),
        os.path.join(SDE_RW, "SDEADM.LINNS_PIDNAMES"),
        os.path.join(SDE_RW, "SDEADM.LINNS_PIDRELATE"),
    ]

    ro_features = [
        os.path.join(SDE_RO, 'SDEADM.LND_parcels', 'SDEADM.LND_parcel_polygon'),
        os.path.join(SDE_RO, 'SDEADM.LND_parcels', "SDEADM.LND_parcel_line"),
    ]

    for db, features in ((SDE_RW, rw_features), (SDE_RO, ro_features)):
        for feature in features:
            feature_metadata = get_sde_metadata(db, feature)

            # Update Metadata
            revised_date = feature_metadata.get("REVISION_DATE")

            if revised_date:
                update_metadata(db, feature, update_attributes)

    # TODO: If working on server MSGISAPPQ203, move all files from C:\Workspace\Parcel_Load\Scratch to your monthly
    #  folder on the file share so that there is an empty Scratch folder on this server for next months Parcel Load.
    input(
        "If working on server MSGISAPPQ203, move all files from C:\Workspace\Parcel_Load\Scratch to your monthly "
        "folder on the file share so that there is an empty Scratch folder on this server for next months Parcel Load."
    )
    # TODO: Do this automatically - script is typically run in the monthly folder

    # Cache Data Update
    # •	On the Caching Server DC1-GIS-APP-P21, run the Cache_Data_Update task in Task Scheduler
    input("On the Caching Server DC1-GIS-APP-P21, run the Cache_Data_Update task in Task Scheduler.")
    
    input("Run Analyze Compress Analyze on Server DC1-GIS-APP-P23.Current runs Saturdays @ 9am (until 10:30am)")

    # Update GOV_OWN_VW
    input("Update GOV-Owned parcel layer - GOV_OWN_VW - Prov_Fed_Parcels: "
          "E:\HRM\Scripts\Python\Modules\gispy\parcelload\Prov_Fed_Parcels\main.py")

    # TODO: Turn this into an imported function

    logger.info(f"{datetime.now()}")
