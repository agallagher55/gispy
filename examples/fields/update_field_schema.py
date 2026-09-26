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

from configparser import ConfigParser

from gispy import utils
from gispy.editor_tracking import turn_off_editor_tracking, turn_on_editor_tracking


arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

log_file = os.path.join(
    os.getcwd(),
    f"{datetime.date.today()}_alter_fields.log"
)

logger = logging.getLogger('locators')
logger.setLevel(logging.DEBUG)

file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)

file_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

config = ConfigParser()
config.read('config.ini')

# VARIABLES
update_feature_info = {
    "SDEADM.LND_grass": [
        {
            "field": "SP_ID",
            "new_type": "TEXT",
            "new_length": 20,
        },
    ]
}


# Functions
def update_field_config(feature, field=None, alias=None, name=None, field_type=None, length=None, nullable=None):
    logger.info(f"Updating field configuration...")

    arcpy.AlterField_management(
        in_table=feature,
        field=field,
        new_field_name=name,
        new_field_alias=alias,
        field_type=field_type,
        field_length=length,
        field_is_nullable=nullable,
        clear_field_alias='#'
    )
    logger.info(arcpy.GetMessages())


LOCAL_GDB = None


def get_local_gdb():
    global LOCAL_GDB

    if LOCAL_GDB is None:
        LOCAL_GDB = utils.create_fgdb()

    return LOCAL_GDB


def convert_populated_field_type(feature, field, name=None, alias=None, field_type=None, length=None, nullable=None):
    """
    AlterField_management refuses to change field_type on a table with rows,
    even if the type isn't actually changing. Depending on ArcGIS Pro
    version this comes back as ERROR 001658 ("Cannot alter field types on
    populated tables") or as the pair ERROR 001623 / ERROR 001662 ("The
    table or feature class is not empty"). Work around it by backing up
    the rows, emptying the table, altering the field, then appending the
    rows back in.

    On a versioned feature class, DeleteRows only removes rows from the
    current edit version's delta state; the base table AlterField checks
    still shows the old rows until the feature is unregistered as
    versioned, which folds all edit states into the base table. So
    unregister as versioned before deleting rows and altering the field,
    then re-register as versioned before appending the rows back.
    """
    local_gdb = get_local_gdb()

    feature_name = os.path.basename(feature).replace("SDEADM.", "").replace("WEBGIS.", "")
    logger.info(f"Backing up '{feature}' to '{local_gdb}'...")
    backup = arcpy.FeatureClassToFeatureClass_conversion(
        in_features=feature,
        out_path=local_gdb,
        out_name=feature_name,
    )[0]

    attribute_rules = arcpy.Describe(feature).attributeRules
    rule_export = None

    if attribute_rules:
        attribute_rules_dir = os.path.join(os.path.dirname(local_gdb), "attribute_rules")
        os.makedirs(attribute_rules_dir, exist_ok=True)

        rule_export = os.path.join(attribute_rules_dir, f"{os.path.basename(feature)}_attributeRules.csv")
        logger.info(f"Exporting and deleting attribute rules for '{feature}'...")
        arcpy.ExportAttributeRules_management(in_table=feature, out_csv_file=rule_export)
        arcpy.DeleteAttributeRule_management(feature, [x.name for x in attribute_rules])

    try:
        turn_off_editor_tracking(feature)
    except arcpy.ExecuteError:
        logger.info(f"Editor tracking not enabled on '{feature}', skipping disable step...")

    is_versioned = arcpy.Describe(feature).isVersioned

    if is_versioned:
        logger.info(f"Unregistering '{feature}' as versioned...")
        arcpy.UnregisterAsVersioned_management(
            in_dataset=feature, keep_edit="KEEP_EDIT", compress_default="COMPRESS_DEFAULT"
        )

    logger.info(f"Deleting rows from '{feature}'...")
    arcpy.DeleteRows_management(feature)
    logger.info(arcpy.GetMessages())

    update_field_config(
        feature=feature, field=field, name=name, alias=alias,
        field_type=field_type, length=length, nullable=nullable,
    )

    if is_versioned:
        logger.info(f"Re-registering '{feature}' as versioned...")
        arcpy.RegisterAsVersioned_management(in_dataset=feature)

    # Reload with editor tracking and attribute rules still off, so the
    # restored rows keep their original ADDBY/MODDATE stamps and don't
    # trigger rule-driven recalculation (e.g. ID sequences) on append
    logger.info(f"Appending backed-up rows back into '{feature}'...")
    arcpy.Append_management(inputs=backup, target=feature, schema_type="NO_TEST")
    logger.info(arcpy.GetMessages())

    if rule_export:
        logger.info(f"Re-importing attribute rules for '{feature}'...")
        arcpy.ImportAttributeRules_management(target_table=feature, csv_file=rule_export)

    try:
        turn_on_editor_tracking(feature)
    except arcpy.ExecuteError:
        logger.info(f"Editor tracking not enabled on '{feature}', skipping re-enable step...")


if __name__ == "__main__":

    separator = "-" * 70

    start_time = time.asctime()
    logger.info(f"Start: {start_time}")
    logger.info(separator)

    PC_NAME = os.environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: {PC_NAME} | Running from: {run_from}...")

    try:

        for dbs in [
            # [
            #     # config.get(run_from, "dev_rw"),
            #     config.get(run_from, "dev_ro"),
            #     config.get(run_from, "dev_web_ro_gdb"),
            # ],
            [
                config.get(run_from, "qa_rw"),
                # config.get(run_from, "qa_ro"),
                # config.get(run_from, "qa_web_ro_gdb"),
            ],
            # [
            #     config.get("SERVER", "prod_rw"),
            #     config.get("SERVER", "prod_ro"),
            #     config.get("SERVER", "prod_web_ro_gdb"),
            # ],
        ]:

            if dbs:
                logger.info(f"Processing dbs: {', '.join(dbs)}...")

                for db in dbs:
                    logger.info(f"DATABASE: {db}")

                    for feature_key, field_infos in update_feature_info.items():

                        update_feature = (
                            feature_key.upper().replace("SDEADM.", "")
                            if db.lower().endswith(".gdb")
                            else feature_key
                        )

                        with arcpy.EnvManager(workspace=db):

                            for field_info in field_infos:

                                field = field_info['field']

                                new_alias = field_info.get('new_alias')
                                new_length = field_info.get('new_length')
                                new_name = field_info.get('new_name')
                                new_type = field_info.get('new_type')
                                new_nullable = field_info.get('new_nullable', '#')

                                try:
                                    update_field_config(
                                        feature=update_feature,
                                        field=field,
                                        name=new_name,
                                        alias=new_alias,
                                        field_type=new_type,
                                        length=new_length,
                                        nullable=new_nullable,
                                    )
                                except arcpy.ExecuteError:
                                    err_msg = arcpy.GetMessages(2)

                                    # "not empty" wording varies by ArcGIS Pro version:
                                    # older Pro raises 001658, newer Pro raises 001623/001662
                                    populated_table_errors = ("001658", "001662")

                                    if any(code in err_msg for code in populated_table_errors):
                                        logger.warning(
                                            f"{err_msg}\n'{update_feature}' is populated; falling back to "
                                            "backup/truncate/alter/append..."
                                        )
                                        convert_populated_field_type(
                                            feature=update_feature,
                                            field=field,
                                            name=new_name,
                                            alias=new_alias,
                                            field_type=new_type,
                                            length=new_length,
                                            nullable=new_nullable,
                                        )
                                    else:
                                        raise

    except arcpy.ExecuteError:
        arcpy_msg = arcpy.GetMessages(2)
        logger.error(arcpy_msg)

    except Exception as e:
        logger.error(e)

        # Return any python specific errors as well as any errors from the geoprocessor
        tb = sys.exc_info()[2]
        tbinfo = traceback.format_tb(tb)[0]
        pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
                str(sys.exc_info()[0]) + ": " + str(sys.exc_info()[1]) + "\n"
        logger.error(pymsg)

        msgs = "GP ERRORS:\n" + arcpy.GetMessages(2) + "\n"
        logger.error(msgs)

        sys.exit()

    # Close the Log File:
    end_time = time.asctime()
    logger.info(separator)
    logger.info(f"End: {end_time}")
