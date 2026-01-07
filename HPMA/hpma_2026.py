import os
import arcpy
import logging
import datetime

from configparser import ConfigParser

from HRMutils import setupLog, create_fgdb

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read('config.ini')

logFile = os.path.join(os.getcwd(), f"{datetime.date.today()}_loggies.log")
logger = setupLog(logFile)

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # print logs to console
logger.setLevel(logging.DEBUG)

# HPMA_FEATURE = r"T:\work\giss\monthly\202511nov\gallaga\HPMA\2024PQI_B2B\2024 HRM PQI - Block to Block.shp"
HPMA_FEATURE = r"T:\work\giss\monthly\202601jan\gallaga\HPMA\2024PQI_B2B-revised\sec_data Events.shp"

def setup_workspace(output_gdb, sde_workspace, hpma_source_feature, reproject=False):
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

    sde_streets = os.path.join(sde_workspace, "SDEADM.TRNLRS_trn_street_vw")
    sde_ast_hpma_ratings = os.path.join(sde_workspace, "SDEADM.AST_hpma_rd_condit_rating")

    gdb_ast_hpma_ratings = os.path.join(output_gdb, "AST_hpma_rd_condit_rating")
    local_hpma_data = os.path.join(output_gdb, "HPMA_ratings")

    print("\nPreparing workspace...")

    if not arcpy.Exists(output_gdb):
        print("\tCreating local geodatabase...")
        output_gdb = create_fgdb(os.getcwd(), "scratch.gdb")

    print("\tExporting filtered streets to local workspace...")
    local_streets = filter_streets(sde_streets, local_gdb)

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

    if reproject:

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

    # streets_sql = f"OWN IN ('HRM', 'NA') AND FLAGS NOT IN ( 'TL' , 'TL ZAG' , 'TL UIMSR' , 'RNV TL', 'NRR TL', 'NAR TL ZAG', 'GSA NRR TL', 'GNP TL', 'DSN TL')"
    streets_sql = f"OWN IN ('HRM', 'NA')"

    print("\nFiltering streets feature...")

    filtered_streets = arcpy.Select_analysis(
        in_features=streets_feature,
        # out_feature_class=os.path.join(output_workspace, "TRN_street_HRMandNA_noTLflag"),
        out_feature_class=os.path.join(output_workspace, "TRN_street_HRM_NA"),
        where_clause=streets_sql
    )[0]

    return filtered_streets


def analyze_features(filtered_streets, hpma_feature, output_workspace, local_ast_hpma_rd_condit_ratings):

    ########################################
    # GET STREETS DATA WITH HPMA DATA
    ########################################

    # 4)	Use the Generate Points Along Lines Tool to create new point feature classes that contain the midpoint of the HPMA
    #     extract lines and the subset of TRN_street created in Step 3.

    # TODO: Create midpoints for streets and hpma segments
    hpma_midpoints = arcpy.GeneratePointsAlongLines_management(
        hpma_feature,
        os.path.join(output_workspace, "hpma_midpoints"),
        "PERCENTAGE",
        None,
        50,
        None
    )[0]

    # Get midpoint of streets (Step 4 in documentation)
    street_midpoints = arcpy.GeneratePointsAlongLines_management(
        filtered_streets,
        os.path.join(output_workspace, os.path.basename(filtered_streets) + "_midpoints"),
        "PERCENTAGE",
        None,
        50,
        None
    )[0]

    # TODO: Spatial join, with 10m buffer, street midpoints with hpma midpoints

    # ==== SPATIAL JOINS ==== #
    print("\nPerforming Spatial Joins...")

    print("Getting nearest street midpoints for HPMA data...")

    # TODO: OR get street midpoints that intersect hpma feature
    # TODO: OR get hpma midpoints that intersect street feature
    hpma_midpoints_w_streets = arcpy.SpatialJoin_analysis(
        hpma_midpoints,
        local_filtered_trn_streets,
        os.path.join(output_workspace, r"hpma_midpoints_w_streets"),
        "JOIN_ONE_TO_ONE",
        # "KEEP_ALL",
        "KEEP_COMMON",
        match_option="INTERSECT",
    )[0]

    # TODO: Get final HPMA line features to append to SDE
    #  Append this feature to SDE feature AST_HPMA_RD_CONDIT
    ast_hpma_rd_condit_trn_street_owned_maintained = arcpy.SpatialJoin_analysis(
        hpma_feature,
        street_midpoints,
        os.path.join(output_workspace, r"ast_hpma_rd_condit_trn_street_owned_maintained"),
        "JOIN_ONE_TO_ONE",
        # "KEEP_ALL",
        "KEEP_COMMON",
        match_option="COMPLETELY_CONTAINS",
    )[0]

    # TODO: Get streets that intersect hpma midpoints
    streets_w_hpma_data = arcpy.SpatialJoin_analysis(
        local_filtered_trn_streets,
        hpma_midpoints,
        os.path.join(output_workspace, r"streets_w_hpma_data"),
        "JOIN_ONE_TO_ONE",
        # "KEEP_ALL",
        "KEEP_COMMON",
        match_option="COMPLETELY_CONTAINS",
    )[0]

    # ... inside analyze_features function ...

    # ########################################
    # LOGIC UPDATE: MANUAL INTERSECT w/ FDMID
    # ########################################

    print("\nStarting Manual Intersect Workflow...")

    # 1. PREP: Add and Calculate 'ORIG_LEN' on the streets
    #    We calculate this on the input so we know the denominator for the percentage.
    print("Calculating baseline street lengths...")
    arcpy.management.AddField(filtered_streets, "ORIG_LEN", "DOUBLE")
    arcpy.management.CalculateGeometryAttributes(filtered_streets, [["ORIG_LEN", "LENGTH_GEODESIC"]], "METERS")

    # 2. INTERSECT: Streets and HPMA
    #    Output Type "LINE" ensures we get the overlapping segments.
    #    We write to 'memory' for speed.
    print("Intersecting layers...")
    intersect_output = r"memory\temp_intersect_segments"

    # join_attributes="ALL" ensures FDMID carries over to the new segments
    arcpy.analysis.Intersect(
        in_features=[filtered_streets, hpma_feature],
        out_feature_class=intersect_output,
        output_type="LINE",
        join_attributes="ALL"
    )

    # 3. CALCULATE: Overlap Percentage
    #    The 'Shape_Length' in the intersect output is the length of the CUT segment.
    #    The 'ORIG_LEN' is the length of the WHOLE street (carried over from step 1).
    print("Calculating overlap percentage...")
    arcpy.management.AddField(intersect_output, "PCT_OVERLAP", "DOUBLE")

    # Equation: Cut Length / Total Length
    calc_expression = "!shape.length! / !ORIG_LEN!"
    arcpy.management.CalculateField(intersect_output, "PCT_OVERLAP", calc_expression, "PYTHON3")

    # 4. FILTER & EXPORT (Simplified)
    #    Select_analysis extracts rows matching the query into a new dataset.
    #    This creates the 'hard' table we need for the join, skipping the View steps.
    print("Filtering for > 50% matches...")

    valid_matches_table = r"memory\valid_hpma_matches"

    # This does the SQL filter and the export in one line
    arcpy.analysis.Select(
        in_features=intersect_output,
        out_feature_class=valid_matches_table,
        where_clause="PCT_OVERLAP > 0.5"
    )

    # 5. CREATE OUTPUT & JOIN
    print("Creating final output layer...")
    streets_w_hpma_data = arcpy.conversion.FeatureClassToFeatureClass(
        filtered_streets,
        output_workspace,
        "streets_w_hpma_data"
    )[0]

    print(f"Joining attributes based on FDMID match...")
    hpma_fields_to_keep = ["PQI_MRM", "HWY_ID"]

    # Join the hard-coded valid matches
    arcpy.management.JoinField(
        in_data=streets_w_hpma_data,
        in_field="FDMID",
        join_table=valid_matches_table,
        join_field="FDMID",
        fields=hpma_fields_to_keep
    )

    # Clean up memory
    arcpy.management.Delete("memory\\temp_intersect_segments")
    arcpy.management.Delete("memory\\valid_hpma_matches")

    return streets_w_hpma_data, ast_hpma_rd_condit_trn_street_owned_maintained


def build_field_mappings_from_dict(target_fc, source_fc, mapping_def):
    """Build a FieldMappings object for Append using a target-first pattern."""

    fms = arcpy.FieldMappings()

    # Very important: add target first, then input
    fms.addTable(target_fc)
    fms.addTable(source_fc)

    for tgt_name, cfg in mapping_def.items():

        idx = fms.findFieldMapIndex(tgt_name)

        if idx == -1:
            arcpy.AddWarning(f"Target field {tgt_name} not found in {target_fc}")
            continue

        fm = fms.getFieldMap(idx)

        # Clear any default inputs (like PCI_MRM -> PCI_MRM)
        for i in range(fm.inputFieldCount - 1, -1, -1):
            fm.removeInputField(i)

        # Wire the source field you want
        fm.addInputField(source_fc, cfg["src_field"])

        # Optionally tweak alias / length (Append may ignore some props but this is safe)
        out_field = fm.outputField
        out_alias = cfg.get("out_alias")
        if out_alias:
            out_field.aliasName = out_alias

        out_length = cfg.get("out_length")
        if out_length and hasattr(out_field, "length"):
            out_field.length = out_length

        fm.outputField = out_field
        fms.replaceFieldMap(idx, fm)

    return fms

if __name__ == "__main__":

    for dbs in [

        [
            config.get("SERVER", "dev_rw"),
        ],

        # [
        #     config.get("SERVER", "qa_rw"),
        # ],

        # [
        #     config.get("SERVER", "prod_rw"),
        # ],

    ]:

        for count, db in enumerate(dbs, start=1):

            logger.info(f"{count}/{len(dbs)}) Database: {db}")

            sde_ro = db.replace("_RW", "_RO")

            sde_streets = os.path.join(db, "SDEADM.TRNLRS_trn_street_vw")
            sde_ast_hpma_ratings_rw = os.path.join(db, "SDEADM.AST_hpma_rd_condit_rating")

            with arcpy.EnvManager(
                    workspace=db,
                    # preserveGlobalIds=True
            ) as env:

                local_gdb = create_fgdb(os.getcwd(), "scratch_Jan6.gdb")

                # Dictionary that drives the mapping
                # key = target field name

                field_mapping_def = {
                    "NUM": {
                        "src_field": "ROUTENUM",
                        "out_alias": "Route Number",
                    },
                    "HWY_ID": {
                        "src_field": "HWY_ID",
                        "out_alias": "Street Name",
                        "out_length": 32,
                    },
                    "BEGIN_DESC": {
                        "src_field": "BEGIN_DESC",
                        "out_alias": "From Street",
                        "out_length": 50,
                    },
                    "END_DESC": {
                        "src_field": "END_DESC",
                        "out_alias": "To Street",
                        "out_length": 50,
                    },
                    "BEGIN_REFP": {
                        "src_field": "BEGIN_REFP",
                        "out_alias": "Start Km Limit of section",
                    },
                    "END_REFP": {
                        "src_field": "END_REFP",
                        "out_alias": "End KM Limit of section",
                    },
                    "DISTRICT": {
                        "src_field": "DISTRICT",
                        "out_alias": "District",
                    },
                    "FUNC_CLASS": {
                        "src_field": "FUNC_CLASS",
                        "out_alias": "Street Class",
                        "out_length": 3,
                    },
                    "ADMIN_SYS": {
                        "src_field": "ADMIN_SYS",
                        "out_alias": "Owner",
                        "out_length": 4,
                    },
                    "LANES": {
                        "src_field": "LANES",
                        "out_alias": "Number of Lanes",
                    },
                    "LENGTH": {
                        "src_field": "LENGTH",
                        "out_alias": "Length",
                    },
                    "WIDTH": {
                        "src_field": "WIDTH",
                        "out_alias": "Width",
                    },
                    "PAVETYPE": {
                        "src_field": "PAVETYPE",
                        "out_alias": "Material",
                        "out_length": 3,
                    },
                    "PCI_YEAR": {
                        "src_field": "PCI_YEAR",
                        "out_alias": "PQI Rating Year",
                    },

                    # This is the important one:
                    # target PCI_MRM should get its value from source PQI_MRM
                    "PCI_MRM": {
                        "src_field": "PQI_MRM",
                        # "out_alias": "PQI Rating",  # optional
                    },
                    # SDATE, SOURCE, SACC, GLOBALID left to target defaults
                }

                # Build mappings
                target_fc = sde_ast_hpma_ratings_rw
                source_fc = HPMA_FEATURE  # your shapefile / layer

                local_filtered_trn_streets, local_hpma, local_sde_ast_hpma = setup_workspace(
                    local_gdb,
                    db,
                    HPMA_FEATURE,
                    reproject=False
                )

                streets_w_hpma_data, ast_hpma_rd_condit_trn_street_owned_maintained = analyze_features(
                    filtered_streets=local_filtered_trn_streets,
                    hpma_feature=local_hpma,
                    output_workspace=local_gdb,
                    local_ast_hpma_rd_condit_ratings=local_sde_ast_hpma
                )

                # TODO: Update me?
                update_sde_ast_hpma = True

                if update_sde_ast_hpma:

                    # 1. Define your inputs
                    #    Update these paths to your actual variables
                    input_dataset = ast_hpma_rd_condit_trn_street_owned_maintained
                    target_dataset = "SDEADM.AST_hpma_rd_condit_rating"

                    print(f"Appending to {input_dataset}...")

                    # 2. Initialize the FieldMappings object
                    #    We start by loading the schema of the TARGET (where data is going TO).
                    #    This ensures we only map fields that actually exist in the destination.
                    fms = arcpy.FieldMappings()
                    fms.addTable(target_dataset)

                    # 3. Define the Explicit Mapping Logic
                    #    Format: "TARGET_FIELD": "SOURCE_FIELD"
                    #    (Based on your provided dictionary and the long string)

                    custom_map_dict = {

                        # "TARGET_FIELD_NAME" : "SOURCE_FIELD_NAME"

                        "FDMID": "FDMID",
                        "HWY_ID": "HWY_ID",
                        "PCI_MRM": "PQI_MRM",  # Mapping PCI_MRM (Target) -> PQI_MRM (Source)
                        # "ROUTENUM": "NUM",
                        "NUM": "ROUTENUM",

                        # Adding the other fields visible in your string to be safe:
                        "BEGIN_DESC": "BEGIN_DESC",
                        "END_DESC": "END_DESC",
                        "BEGIN_REFP": "BEGIN_REFP",
                        "END_REFP": "END_REFP",
                        "DISTRICT": "DISTRICT",
                        "FUNC_CLASS": "FUNC_CLASS",
                        "ADMIN_SYS": "ADMIN_SYS",
                        "LANES": "LANES",
                        "LENGTH": "LENGTH",
                        "WIDTH": "WIDTH",
                        "PAVETYPE": "PAVETYPE",
                        "PCI_YEAR": "PCI_YEAR"
                    }

                    # 4. Loop through and apply the mapping
                    #    This finds the Target FieldMap, edits it to look at the Source Field, and saves it back.
                    for target_field, source_field in custom_map_dict.items():

                        # Check if the target field actually exists in the FieldMappings (safe check)
                        try:
                            # Get the FieldMap for the specific target field
                            fm = fms.getFieldMap(fms.findFieldMapIndex(target_field))

                            # Add the input field (source) to this FieldMap
                            # This tells ArcPy: "For this target column, grab data from this source column"
                            fm.addInputField(input_dataset, source_field)

                            # Update the FieldMappings object with the modified FieldMap
                            fms.replaceFieldMap(fms.findFieldMapIndex(target_field), fm)

                            print(f"Mapped: {target_field} <== {source_field}")

                        except Exception as e:
                            print(f"WARNING: Could not map {target_field}. It might not exist in the target schema.")

                    # 5. Run the Append with the Object
                    arcpy.Append_management(
                        inputs=input_dataset,
                        target=target_dataset,
                        schema_type="NO_TEST",
                        field_mapping=fms,  # Pass the object here, not the string
                        update_geometry="NOT_UPDATE_GEOMETRY"
                    )
                    print(arcpy.GetMessages())

                    # Calculate fields
                    print("Calculating fields...")
                    print("Updating SDATE field with ADDDATE value...")
                    arcpy.management.CalculateField(
                        in_table=sde_ast_hpma_ratings_rw,
                        field="SDATE",
                        expression="!ADDDATE!",
                        expression_type="PYTHON3",
                        code_block="",
                        field_type="TEXT",
                        enforce_domains="NO_ENFORCE_DOMAINS"
                    )
                    print(arcpy.GetMessages())

                    # SOURCE field
                    print("Updating SOURCE field with 'TPW'...")
                    arcpy.CalculateField_management(
                        in_table=sde_ast_hpma_ratings_rw,
                        field="SOURCE",
                        expression="'TPW'",
                        expression_type="PYTHON3",
                        code_block="",
                        field_type="TEXT",
                        enforce_domains="NO_ENFORCE_DOMAINS"
                    )
                    print(arcpy.GetMessages())

                    print(f"Updating RO feature...")

                    sde_ast_hpma_ratings_ro = os.path.join(sde_ro, "SDEADM.AST_hpma_rd_condit_rating")

                    with arcpy.EnvManager(preserveGlobalIds=True):
                        arcpy.management.Append(
                            inputs=sde_ast_hpma_ratings_rw,  # RW
                            target=sde_ast_hpma_ratings_ro,  # RO
                            schema_type="TEST",
                            field_mapping=None,
                            subtype="",
                            expression="",
                            match_fields=None,
                            update_geometry="NOT_UPDATE_GEOMETRY"
                        )
                        print(arcpy.GetMessages())

                # TRUNCATE AND LOAD RO ASDEADM.TRN_Street_HPMA_Ratings"

                update_trn_street_hpma_ratings = True

                if update_trn_street_hpma_ratings:

                    sde_trn_street_hpma_ratings = os.path.join(sde_ro, "SDEADM.TRN_Street_HPMA_Ratings")

                    print(f"Updating {sde_trn_street_hpma_ratings}...")

                    arcpy.TruncateTable_management(
                        in_table=sde_trn_street_hpma_ratings
                    )

                    # 1. Define your inputs
                    input_dataset = streets_w_hpma_data
                    target_dataset = sde_trn_street_hpma_ratings

                    # 2. Initialize the FieldMappings object
                    #    Load the schema from the TARGET so we know exactly what fields we need to fill.
                    fms = arcpy.FieldMappings()
                    fms.addTable(target_dataset)

                    # 3. Define the Explicit Mapping Logic
                    #    Format: "TARGET_FIELD_NAME" : "SOURCE_FIELD_NAME"
                    custom_map_dict = {
                        "FULL_NAME": "FULL_NAME",
                        "FDMID": "FDMID",
                        "HWY_ID": "HWY_ID",  # In your string, source was HWY_ID
                        "PCI_MRM": "PQI_MRM"  # Target PCI_MRM gets data from Source PQI_MRM
                    }

                    # 4. Loop through and apply the mapping
                    print(f"Mapping fields from {input_dataset} to {target_dataset}...")

                    for target_field, source_field in custom_map_dict.items():
                        try:
                            # Find the definition of the target field
                            fm_index = fms.findFieldMapIndex(target_field)

                            if fm_index != -1:
                                fm = fms.getFieldMap(fm_index)

                                # Explicitly tell ArcPy: "Fill this target field using this source field"
                                fm.addInputField(input_dataset, source_field)

                                # Update the main mapping object
                                fms.replaceFieldMap(fm_index, fm)
                                print(f"  Mapped: {target_field} <== {source_field}")
                            else:
                                print(f"  WARNING: Target field '{target_field}' not found in {target_dataset}")

                        except Exception as e:
                            print(f"  ERROR mapping {target_field}: {str(e)}")

                    # 5. Run the Append
                    print("Appending data...")
                    arcpy.management.Append(
                        inputs=input_dataset,
                        target=target_dataset,
                        schema_type="NO_TEST",
                        field_mapping=fms,
                        update_geometry="NOT_UPDATE_GEOMETRY"
                    )
                    print("Append complete.")
