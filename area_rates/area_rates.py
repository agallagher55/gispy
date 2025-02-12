"""
    Models
    SQL
    QA

    BID: LND_area_rate_bid
    Commercial: SDEADM.LND_area_rate_ComFac_Serv
    Regional Transit: SDEADM.LND_area_rate_reg_trans
    Transit: SDEADM.LND_area_rate_transit
    Tax Designation: SDEADM.ADM_finance_boundaries/SDEADM.ADM_tax_designation

    Fire Protection: SDEADM.LND_area_rate_fire_protection --> Done differently
    Private Roads: SDEADM.LND_area_rate_Priv_Road --> Done differently
"""

import arcpy
import os

from datetime import datetime

from utils import create_fgdb

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

AREA_RATE_FEATURES = {
    # "LND_area_rate_ComFac_Serv": {},
    #
    # "LND_area_rate_bid": {},
    # "LND_area_rate_transit": {},
    #
    # "LND_area_rate_fire_protection": {},
    # "ADM_finance_boundaries//ADM_tax_designation": {},
    # "LND_area_rate_commercial": {},
    # "LND_area_rate_stormwater": {},

    "LND_area_rate_Priv_Road": {},
}

AREA_RATE_FINAL_FEATURE_UPDATE_NAME = "SDEADM.Area_Rates_PID_AAN"

# SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
SDE = r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde"

PARCELS = os.path.join(SDE, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

SQL_SCRIPT_DIR = r"T:\work\giss\tools\Area_Rates"

YEAR = datetime.now().year



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

    print(f"\nRunning PID Area Rate Summary on {area_rate_feature_name}...")

    print(f"\tRunning Identity analysis...")
    identity_feature = arcpy.Identity_analysis(
        in_features=parcel_polygons,
        identity_features=area_rate_feature,
        out_feature_class=os.path.join(local_workspace, f"{area_rate_feature_name}_identity"),
        join_attributes="ALL",
        cluster_tolerance="",
        relationship="NO_RELATIONSHIPS"
    )[0]

    print(f"\tExporting result of Frequency analysis to {final_feature}...")
    boundary_parcels_sde_feature = arcpy.Frequency_analysis(
        in_table=identity_feature,
        out_table=final_feature,
        frequency_fields=["PID", "AREARATE_CODE"],
        summary_fields=["SHAPE_area"]
    ).getOutput(0)

    # TODO: Add

    return boundary_parcels_sde_feature


def private_roads(sde_workspace, output_workspace):
    print(f"\nPrivate Roads Area Rate analysis...")

    sde_private_roads_ar_boundary = os.path.join(sde_workspace, "SDEADM.LND_area_rate_Priv_Road")
    sde_parcels = os.path.join(sde_workspace, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

    with arcpy.EnvManager(workspace=r"C:\Workspace\Area_Rate_Overlay\Area_Rate.gdb"):

        print("\nExporting Parcels...")
        local_parcels = arcpy.conversion.FeatureClassToFeatureClass(
            in_features=sde_parcels,
            out_path=output_workspace,
            out_name="Parcel",
        )[0]

        # Export feature classes
        for i in range(22):
            area_rate_code = f"R{str(i * 10).zfill(3)}"

            print(f"\n{area_rate_code}")

            sql = f"AREARATE_CODE = '{area_rate_code}'"

            # Export Area Code feature
            print("\tExporting Area Rate code boundary...")
            local_area_code_boundary = arcpy.conversion.FeatureClassToFeatureClass(
                in_features=sde_private_roads_ar_boundary,
                out_path=output_workspace,
                out_name=f"Local_{area_rate_code}",
                where_clause=sql,
                # field_mapping="ARCODE_RES \"Area Rate Code - Res\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_RES,0,6;ARCODE_COM \"Area Rate Code - Com\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_COM,0,6;DESCRIP \"Description\" true true false 50 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,DESCRIP,0,50;DOCUMENT \"Document\" true true false 80 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,DOCUMENT,0,80;FCODE \"FCODE\" true true false 12 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,FCODE,0,12;SOURCE \"Source\" true true false 12 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SOURCE,0,12;SACC \"Source Accuracy\" true true false 2 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SACC,0,2;SDATE \"Input Date\" true true false 8 Date 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,SDATE,-1,-1;OPERATOR \"Operator\" true true false 8 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,OPERATOR,0,8;ARCODE_RCE \"Area Rate Code - Rce\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,ARCODE_RCE,0,6;GLOBALID \"GLOBALID\" false false true 38 GlobalID 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,GLOBALID,-1,-1;AREARATE_CODE \"Area Rate Code\" true true false 6 Text 0 0,First,#,E:\\HRM\\Scripts\\SDE\\qa_RW_sdeadm.sde\\SDEADM.LND_area_rate_Priv_Road,AREARATE_CODE,0,6",
                # config_keyword=""
            )[0]

            # Identity
            print(f"\tIdentity Analysis...")
            identity_feature = arcpy.analysis.Identity(
                in_features=local_parcels,
                identity_features=local_area_code_boundary,
                out_feature_class=os.path.join(output_workspace, f"Local_{area_rate_code}_Identity"),
                join_attributes="ALL",
                cluster_tolerance="",
                relationship="NO_RELATIONSHIPS"
            )[0]

            # Frequency
            print(f"\tFrequency Analysis...")
            arcpy.analysis.Frequency(
                in_table=identity_feature,
                out_table=os.path.join(sde_workspace, f"SAP_PrivRd_{area_rate_code}_compare"),
                frequency_fields=["PID", "AREARATE_CODE"],
                summary_fields=["SHAPE_area"]
            )


if __name__ == "__main__":

    # TODO: Put all variables in a config file

    prod_sde = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"

    # local_workspace = create_fgdb(out_folder_path=os.getcwd())
    local_workspace = r"T:\work\giss\tools\Area_Rates\v2024_SUMMER - SAP\scratch.gdb"

    for sde_workspace in [
        # r"E:\HRM\Scripts\SDE\dev_RW_sdeadm.sde",
        # r"E:\HRM\Scripts\SDE\qa_RW_sdeadm.sde",
        # r"E:\HRM\Scripts\SDE\prod_RW_sdeadm.sde",

        r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde"
        # r"E:\HRM\Scripts\SDE\SQL Server\qa_RW_sdeadm.sde"
    ]:
        print(f"\n{datetime.now()}")

        print(f"WORKSPACE: {sde_workspace}")

        num_area_rate_features = len(AREA_RATE_FEATURES)

        with arcpy.EnvManager(workspace=sde_workspace):
            for count, feature in enumerate(AREA_RATE_FEATURES, start=1):

                print(f"\n{count}/{num_area_rate_features}) {feature}")

                feature_name = os.path.basename(feature)
                sql = AREA_RATE_FEATURES.get(feature_name)  # Not currently used

                if feature_name == "LND_area_rate_Priv_Road":
                    private_roads(sde_workspace, local_workspace)

                try:
                    # Create AR_XXX tables through overlay analysis
                    out_table = boundary_parcels(feature, local_workspace, sde_workspace, PARCELS)

                except arcpy.ExecuteError:
                    print(arcpy.GetMessages(2))

        print(f"\n{datetime.now()}")

    input(f"Run SQL scripts next.")
