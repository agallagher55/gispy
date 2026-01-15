"""
    Models
    SQL
    QA

    ADVANCED USER LICENSE NEEDED

    BID: LND_area_rate_bid
    Commercial: SDEADM.LND_area_rate_ComFac_Serv
    Regional Transit: SDEADM.LND_area_rate_reg_trans
    Transit: SDEADM.LND_area_rate_transit
    Active Transportation: SDEADM.LND_area_rate_active_trans
    Tax Designation: SDEADM.ADM_finance_boundaries/SDEADM.ADM_tax_designation

    Fire Protection: SDEADM.LND_area_rate_fire_protection --> Done differently
    Private Roads: SDEADM.LND_area_rate_Priv_Road --> Done differently
"""

import arcpy
import os
import configparser
import logging

from datetime import datetime

from utils import create_fgdb

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

logger = logging.getLogger(__name__)

logging.basicConfig(
    filename="area_rates.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Create formatter and add to handler
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')
console_handler.setFormatter(formatter)

# Add handler to the logger
logger.addHandler(console_handler)

SQL_SCRIPT_DIR = r"T:\work\giss\tools\Area_Rates"

PROD_SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
PARCELS = os.path.join(PROD_SDE, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

YEAR = datetime.now().year

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "area_rates.ini")


def load_area_rate_features(config_path=CONFIG_PATH):
    """Read area rate feature names from configuration file."""

    config = configparser.ConfigParser()
    config.read(config_path)

    features_lines = config.get("AreaRates", "features", fallback="")
    features = sorted([line.strip() for line in features_lines.splitlines() if line.strip()])

    return features


def boundary_parcels(area_rate_feature, local_workspace, sde, parcel_polygons):
    """
    - Replace the model used to create frequency table, SAP_{area rate}
        BID: LND_area_rate_bid
        Commercial: SDEADM.LND_area_rate_ComFac_Serv
        Regional Transit: SDEADM.LND_area_rate_reg_trans
        Transit: SDEADM.LND_area_rate_transit
        Tax Designation: SDEADM.ADM_finance_boundaries/SDEADM.ADM_tax_designation

        --> results from model match results from this function. (except tax_des includes PIDs without an Area Rate)

    - If you need/want to use a local copy of parcels, set local parcels as parcel_polygons parameter.

    :param area_rate_feature:
    :param local_workspace: where the final feature will be stored
    :return: SAP_{area rate} - feature table
    """

    area_rate_feature_name = arcpy.Describe(area_rate_feature).name.replace("SDEADM.", "")
    area_rate = area_rate_feature_name.replace("LND_area_rate_", "")

    final_feature = os.path.join(sde, f"SAP_{area_rate}")

    logger.info(f"Running PID Area Rate Summary on {area_rate_feature_name}...")

    logger.info(f"\tRunning Identity analysis...")
    identity_feature = arcpy.Identity_analysis(
        in_features=parcel_polygons,
        identity_features=area_rate_feature,
        out_feature_class=os.path.join(local_workspace, f"{area_rate_feature_name}_identity"),
        join_attributes="ALL",
        cluster_tolerance="",
        relationship="NO_RELATIONSHIPS"
    )[0]

    logger.info(f"\tExporting result of Frequency analysis to {final_feature}...")
    boundary_parcels_sde_feature = arcpy.Frequency_analysis(
        in_table=identity_feature,
        out_table=final_feature,
        frequency_fields=["PID", "AREARATE_CODE"],
        summary_fields=["SHAPE_area"]
    ).getOutput(0)

    return boundary_parcels_sde_feature


def private_roads(sde_workspace, output_workspace):
    logger.info(f"Private Roads Area Rate analysis...")

    sde_private_roads_ar_boundary = os.path.join(sde_workspace, "SDEADM.LND_area_rate_Priv_Road")
    sde_parcels = os.path.join(sde_workspace, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

    with arcpy.EnvManager(workspace=r"C:\Workspace\Area_Rate_Overlay\Area_Rate.gdb"):

        logger.info("Exporting Parcels...")
        local_parcels = arcpy.conversion.FeatureClassToFeatureClass(
            in_features=sde_parcels,
            out_path=output_workspace,
            out_name="Parcel",
        )[0]

        # Export feature classes
        for i in range(22):
            area_rate_code = f"R{str(i * 10).zfill(3)}"

            logger.info(f"{area_rate_code}")

            sql = f"AREARATE_CODE = '{area_rate_code}'"

            # Export Area Code feature
            logger.info("\tExporting Area Rate code boundary...")
            local_area_code_boundary = arcpy.conversion.FeatureClassToFeatureClass(
                in_features=sde_private_roads_ar_boundary,
                out_path=output_workspace,
                out_name=f"Local_{area_rate_code}",
                where_clause=sql,
                # field_mapping="ARCODE_RES \"Area Rate Code - Res\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_RES,0,6;ARCODE_COM \"Area Rate Code - Com\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_COM,0,6;DESCRIP \"Description\" true true false 50 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,DESCRIP,0,50;DOCUMENT \"Document\" true true false 80 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,DOCUMENT,0,80;FCODE \"FCODE\" true true false 12 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,FCODE,0,12;SOURCE \"Source\" true true false 12 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SOURCE,0,12;SACC \"Source Accuracy\" true true false 2 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SACC,0,2;SDATE \"Input Date\" true true false 8 Date 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SDATE,-1,-1;OPERATOR \"Operator\" true true false 8 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,OPERATOR,0,8;ARCODE_RCE \"Area Rate Code - Rce\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_RCE,0,6;GLOBALID \"GLOBALID\" false false true 38 GlobalID 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,GLOBALID,-1,-1;AREARATE_CODE \"Area Rate Code\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,AREARATE_CODE,0,6",
                # config_keyword=""
            )[0]

            # Identity
            logger.info(f"\tIdentity Analysis...")
            identity_feature = arcpy.Identity_analysis(
                in_features=local_parcels,
                identity_features=local_area_code_boundary,
                out_feature_class=os.path.join(output_workspace, f"Local_{area_rate_code}_Identity"),
                join_attributes="ALL",
                cluster_tolerance="",
                relationship="NO_RELATIONSHIPS"
            )[0]

            # Frequency
            logger.info(f"\tFrequency Analysis...")
            arcpy.analysis.Frequency(
                in_table=identity_feature,
                out_table=os.path.join(sde_workspace, f"SAP_PrivRd_{area_rate_code}_compare"),
                frequency_fields=["PID", "AREARATE_CODE"],
                summary_fields=["SHAPE_area"]
            )


def archive_data(archive_folder, sde_workspace):
    logger.info("Archiving data...")

    # Create geodatabase
    archive_gdb = arcpy.CreateFileGDB_management(archive_folder, "final_features_archive.gdb")[0]

    with arcpy.EnvManager(workspace=sde_workspace):
        # all_tables = arcpy.ListTables()
        final_tables = arcpy.ListTables("*_FINAL_SAP")
        logger.info(final_tables)

        for table in final_tables:
            table_name = arcpy.Describe(table).baseName.split(".")[-1]

            logger.info(f"\tArchiving '{table_name}'...")
            arcpy.conversion.TableToTable(
                in_rows=table,
                out_path=archive_gdb,
                out_name=table_name
            )

        # Archive parcels used during process


if __name__ == "__main__":

    # Read area rate feature list from configuration
    # area_rate_features = load_area_rate_features()
    area_rate_features = ["LND_area_rate_transit", ]

    local_workspace = create_fgdb(out_folder_path=os.getcwd())
    # local_workspace = r"T:\work\giss\monthly\202508aug\gallaga\area_rates\scratch.gdb"

    for sde_workspace in [
        r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde",
        # r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
    ]:
        logger.info(f"{datetime.now()}")

        logger.info(f"WORKSPACE: {sde_workspace}")

        num_area_rate_features = len(area_rate_features)

        with arcpy.EnvManager(workspace=sde_workspace):

            for count, feature in enumerate(area_rate_features, start=1):

                logger.info(f"{count}/{num_area_rate_features}) {feature}")

                feature_name = os.path.basename(feature)

                if feature_name == "LND_area_rate_Priv_Road":
                    private_roads(sde_workspace, local_workspace)

                elif feature_name == "LND_area_rate_transit":
                    feature = arcpy.Select_analysis(
                        in_features=feature_name,
                        out_feature_class=os.path.join(local_workspace, feature_name),
                        where_clause=f"DESCRIP LIKE '{YEAR} Local Transit"
                        # where_clause = f"DESCRIP LIKE '2025 Local Transit'"
                    )[0]

                try:
                    # Create AR_XXX tables through overlay analysis
                    out_table = boundary_parcels(feature, local_workspace, sde_workspace, PARCELS)

                except arcpy.ExecuteError:
                    logger.error(arcpy.GetMessages(2))

        logger.info(f"{datetime.now()}")

    input(f"Run SQL scripts next.")
