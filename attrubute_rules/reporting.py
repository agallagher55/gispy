# Converted from Full_Automation_Script_No_Prefix.ipynb

import arcpy
import os
import argparse

# Local variables and constants
DEFAULT_WORKSPACE = r"C:\GISData\Project.gdb"
DEFAULT_OUTPUT_DIR = r"C:\GISOutputs"
DEFAULT_LOG_FILE = r"C:\Logs\automation.log"


def initialize_logging(log_path):
    """
    Sets up logging to write messages to both console and a log file.
    """
    import logging
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    # File handler
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)


def list_feature_classes(workspace):
    """
    Returns a list of feature classes in the given workspace.
    """
    arcpy.env.workspace = workspace
    return arcpy.ListFeatureClasses()


def export_features_to_shapefile(feature_class, output_dir):
    """Export the feature class to a shapefile and return its path."""
    shp_name = os.path.basename(feature_class) + ".shp"
    out_path = os.path.join(output_dir, shp_name)
    arcpy.FeatureClassToShapefile_conversion(feature_class, output_dir)
    print(f"Exported {feature_class} to {out_path}")
    return out_path


def apply_field_calculator(
    feature_class,
    field_name,
    expression,
    expression_type="PYTHON3",
):
    """Apply a field calculation on the given feature class."""
    arcpy.CalculateField_management(
        feature_class,
        field_name,
        expression,
        expression_type,
    )


def main(workspace, output_dir, log_file):
    """Run the export and field calculation workflow."""
    initialize_logging(log_file)

    try:
        fcs = list_feature_classes(workspace)
        for fc in fcs:
            export_features_to_shapefile(fc, output_dir)

        # Example field calculation
        sample_fc = fcs[0] if fcs else None
        if sample_fc:
            apply_field_calculator(
                sample_fc,
                "NewField",
                "!ExistingField! * 2",
            )

    except Exception as e:
        import logging
        logging.error(f"An error occurred: {e}")


if __name__ == "__main__":
    main(workspace, output_dir, log_file)
