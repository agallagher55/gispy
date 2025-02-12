import arcpy
import re

TRN_street = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\TRN_street"
AST_hpma_rd_condit_rating = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\AST_hpma_rd_condit_rating"

TRN_street_Points = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\TRN_street_Points"
HPMA_Point = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\HPMA_Point"
Street_HPMA_Pnt_SJ = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\Street_HPMA_Pnt_SJ"
Street_HPMA_Pnt_SJ_Calc = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\Street_HPMA_Pnt_SJ_Calc"
TRN_STREET_HPMA_RATINGS = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb\\TRN_Street_HPMA_Ratings"

TRN_street_Layer = "TRN_street_Layer"
AST_hpma_rd_condit_rating_Layer = "AST_hpma_rd_condit_rating_Layer"
Street_HPMA_Pnt_SJ_Layer = "Street_HPMA_Pnt_SJ_Layer"
Street_Match_HPMA_Layer = "Street_Match_HPMA_Layer"

if __name__ == "__main__":

    arcpy.env.workspace = "T:\\work\\giss\\monthly\\202109sep\\potterm\\01_HPMA_Street_Process\\Test.gdb"

    # Process: Make Feature Layer

    arcpy.MakeFeatureLayer_management(
        TRN_street,
        TRN_street_Layer,
        "OWN in ('HRM', 'NA') AND FLAGS not in ('TL', 'TL ZAG', 'TL UIMSR', 'RNV TL', 'NRR TL', 'NAR TL ZAG', 'GSA NRR TL', 'GNP TL', 'DSN TL')",
        "",
        "OBJECTID OBJECTID VISIBLE NONE;SHAPE SHAPE HIDDEN NONE;FCODE FCODE HIDDEN NONE;STR_NAME STR_NAME VISIBLE NONE;STR_TYPE STR_TYPE VISIBLE NONE;FULL_NAME FULL_NAME VISIBLE NONE;MUN_CODE MUN_CODE HIDDEN NONE;FROM_STR FROM_STR HIDDEN NONE;TO_STR TO_STR HIDDEN NONE;STR_DIR STR_DIR HIDDEN NONE;STR_STATUS STR_STATUS HIDDEN NONE;ST_CLASS ST_CLASS HIDDEN NONE;OWN OWN VISIBLE NONE;MAINTENANCE MAINTENANCE HIDDEN NONE;DATE_ACCEPT DATE_ACCEPT HIDDEN NONE;FROM_ELEV FROM_ELEV HIDDEN NONE;TO_ELEV TO_ELEV HIDDEN NONE;STR_REM STR_REM HIDDEN NONE;PSAB_CODE PSAB_CODE HIDDEN NONE;FLAGS FLAGS HIDDEN NONE;ACC ACC HIDDEN NONE;SOURCE SOURCE HIDDEN NONE;DATE_ACT DATE_ACT HIDDEN NONE;TECH_ACT TECH_ACT HIDDEN NONE;SYS_DATE SYS_DATE HIDDEN NONE;FDMID FDMID VISIBLE NONE;ROUTE_ID ROUTE_ID HIDDEN NONE;FROM_LEFT FROM_LEFT VISIBLE NONE;TO_LEFT TO_LEFT VISIBLE NONE;FROM_RIGHT FROM_RIGHT VISIBLE NONE;TO_RIGHT TO_RIGHT VISIBLE NONE;OLD_FDMID OLD_FDMID HIDDEN NONE;GSA_LEFT GSA_LEFT VISIBLE NONE;GSA_RIGHT GSA_RIGHT HIDDEN NONE;PAR_LEFT PAR_LEFT HIDDEN NONE;PAR_RIGHT PAR_RIGHT HIDDEN NONE;STR_CODE_L STR_CODE_L HIDDEN NONE;STR_CODE_R STR_CODE_R HIDDEN NONE;ASSETID ASSETID HIDDEN NONE;MAINTSUMMER MAINTSUMMER HIDDEN NONE;SHAPE_Length SHAPE_Length VISIBLE NONE"
    )

    # Process: Generate Points Along Lines
    arcpy.GeneratePointsAlongLines_management(
        TRN_street_Layer,
        TRN_street_Points,
        "PERCENTAGE",
        "",
        "50",
        ""
    )

    #arcpy.MakeFeatureLayer_management(AST_hpma_rd_condit_rating, AST_hpma_rd_condit_rating_Layer, "", "", "OBJECTID OBJECTID VISIBLE NONE;SHAPE SHAPE VISIBLE NONE;NUM NUM HIDDEN NONE;HWY_ID HWY_ID VISIBLE NONE;BEGIN_DESC BEGIN_DESC HIDDEN NONE;END_DESC END_DESC HIDDEN NONE;BEGIN_REFP BEGIN_REFP HIDDEN NONE;END_REFP END_REFP HIDDEN NONE;DISTRICT DISTRICT HIDDEN NONE;FUNC_CLASS FUNC_CLASS VISIBLE NONE;ADMIN_SYS ADMIN_SYS HIDDEN NONE;LANES LANES HIDDEN NONE;LENGTH LENGTH HIDDEN NONE;WIDTH WIDTH HIDDEN NONE;PAVETYPE PAVETYPE HIDDEN NONE;PCI_MRM PCI_MRM VISIBLE NONE;PCI_YEAR PCI_YEAR HIDDEN NONE;ADDBY ADDBY HIDDEN NONE;MODBY MODBY HIDDEN NONE;ADDDATE ADDDATE HIDDEN NONE;MODDATE MODDATE HIDDEN NONE;SDATE SDATE HIDDEN NONE;SOURCE SOURCE HIDDEN NONE;SACC SACC HIDDEN NONE;SHAPE_Length SHAPE_Length VISIBLE NONE")
    arcpy.MakeFeatureLayer_management(AST_hpma_rd_condit_rating, AST_hpma_rd_condit_rating_Layer)

    # Process: Generate Points Along Lines (2)
    arcpy.GeneratePointsAlongLines_management(
        AST_hpma_rd_condit_rating_Layer,
        HPMA_Point,
        "PERCENTAGE",
        "",
        "50",
        ""
    )

    # Process: Spatial Join
    arcpy.SpatialJoin_analysis(
        TRN_street_Points,
        HPMA_Point,
        Street_HPMA_Pnt_SJ,
        "JOIN_ONE_TO_ONE",
        "KEEP_ALL",
        "#",
        "CLOSEST",
        "10 Meters",
        "DIST"
    )

    # Remove characters from end of HWY_ID field
    code_block = '''import re
    def update_hwyID(HWY_ID):
        return re.sub(r"""\ \[.*\]""","", HWY_ID)'''
    expression = "update_hwyID(!HWY_ID!)"

    # Replace a layer/table view name with a path to a dataset (which can be a layer file) or create the layer/table view within the script
    # The following inputs are layers or table views: "Calc_Test"
    arcpy.CalculateField_management(Street_HPMA_Pnt_SJ, "HWY_ID", expression, "PYTHON_9.3", code_block)

    # Use spatial joined layer to truncate and load data into TRN_STREET_HPMA_RATINGS
    arcpy.MakeFeatureLayer_management(Street_HPMA_Pnt_SJ, Street_Match_HPMA_Layer)
    arcpy.SelectLayerByAttribute_management(Street_Match_HPMA_Layer, "NEW_SELECTION", "FULL_NAME = HWY_ID")
    arcpy.MakeTableView_management(Street_Match_HPMA_Layer, "Street_Match_HPMA_View")

    arcpy.TruncateTable_management(TRN_STREET_HPMA_RATINGS)
    arcpy.Append_management("Street_Match_HPMA_View", TRN_STREET_HPMA_RATINGS, "NO_TEST")
    # arcpy.CopyFeatures_management("Street_Match_HPMA_Layer", "Street_Match_HPMA")

    print("All done")

    # TODO
    # Create Point FC called TRN_Street_HPMA_Rating_FC or make feature layer with only the fields we want and then
    # Append Data from Street_Match_HPMA into TRN_Street_HPMA_Rating_FC
    # Export TRN_Street_HPMA_Rating_FC to a table called TRN_Street_HPMA_Rating
    # Truncate TRN_Street_HPMA_Rating in RO
    # load data from TRN_Street_HPMA_Rating in FGDB into TRN_Street_HPMA_Rating in RO
