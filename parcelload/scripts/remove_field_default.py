import os
import arcpy
import logging
import datetime

from configparser import ConfigParser

from hrmutils.HRMutils import setupLog

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

if __name__ == "__main__":

    for dbs in [
        # [utils.create_fgdb(out_folder_path=CURRENT_DIR, out_name="scratch.gdb")],
        # [
        #     config.get("SERVER", "dev_ro"),
        # ],
        # [
        #     config.get("SERVER", "qa_ro"),
            # config.get("SERVER", "qa_web_ro_gdb"),
        # ],
        [
            config.get("SERVER", "prod_ro"),
        ],

    ]:

        # TODO: Web RO GDB features
        # with arcpy.EnvManager(workspace=config.get("SERVER", "prod_web_ro_gdb")):
        #
        #     logger.info("Getting feature classes...")
        #     web_ro_features = arcpy.ListFeatureClasses()
        #     print()

        for count, db in enumerate(dbs, start=1):

            logger.info(f"{count}/{len(dbs)}) Database: {db}")

            with arcpy.EnvManager(workspace=db):

                logger.info("Getting feature classes...")

                # Get all feature datasets
                db_feature_datasets = sorted(arcpy.ListDatasets())

                # Start with SDEADM features at the root level
                db_features = arcpy.ListFeatureClasses(wild_card="*SDEADM*")

                # Add SDEADM features from within each feature dataset
                for dataset in db_feature_datasets:
                    features_in_dataset = arcpy.ListFeatureClasses(wild_card="*SDEADM*", feature_dataset=dataset)
                    db_features.extend(features_in_dataset)

                # TODO: Get features in feature datasets

                # for feature_class in web_ro_features:
                for count, feature_class in enumerate(db_features, start=1):

                    # feature_class = f"SDEADM.{feature_class}"

                    logger.info("=" * 75)
                    logger.info(f"{count}/{len(db_features)}) {feature_class}")
                    logger.info("=" * 75)

                    if arcpy.Exists(feature_class):

                        # Get field defaults
                        logger.info("Getting field defaults...")
                        fields = [x for x in arcpy.ListFields(feature_class) if x.defaultValue]

                        if fields:

                            for field in fields:

                                # Remove field default
                                logger.info(f"Removing field default of {field.defaultValue} from '{field.name}'...")
                                arcpy.AssignDefaultToField_management(
                                    in_table=feature_class,
                                    field_name=field.name,
                                    clear_value="CLEAR_VALUE"
                                )
                                print(arcpy.GetMessages())
