import os
import arcpy
import logging
import datetime

import attr_rules

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


def query_all_feature(workspace: str, wildcard: str = "*", include_datasets = True):

    print(f"\nQuerying all features in '{workspace}'...")

    with arcpy.EnvManager(workspace=workspace):

        features = arcpy.ListFeatureClasses(wild_card=wildcard)
        tables = arcpy.ListTables(wild_card=wildcard)

        if include_datasets:

            datasets = arcpy.ListDatasets(wild_card=wildcard)

            for dataset in datasets:

                dataset_features = arcpy.ListFeatureClasses(
                    feature_dataset=dataset,
                    wild_card=wildcard
                )

                features.extend(dataset_features)

    return features + tables


if __name__ == "__main__":

    separator = 79 * "="

    check_rules = False

    rw_db = config.get("SERVER", "dev_rw")
    ro_db = config.get("SERVER", "dev_ro")

    rw_features = query_all_feature(rw_db, wildcard="*LND_*")
    ro_features = query_all_feature(ro_db, wildcard="*LND_*")

    # Sort features
    # Filter features
    # Compare features
    print()

    for dbs in [
        [
            config.get("SERVER", "dev_ro"),
        ],
        # [
        #     config.get("SERVER", "qa_ro"),
        # ],
        # [
        #     config.get("SERVER", "prod_ro"),
        # ],

    ]:

        for count, db in enumerate(dbs, start=1):

            logger.info(f"{count}/{len(dbs)}) Database: {db}")

            with arcpy.EnvManager(workspace=db):

                if check_rules:

                    features_with_rules = list()

                    all_features = query_all_feature(db)

                    num_features = len(all_features)

                    for count, feature in enumerate(all_features, start=1):
                        print(separator)
                        print(f"\n{count}/{num_features}) {feature}")
                        print(f"\tGetting rules...")

                        rules = attr_rules.get_rules(feature)

                        if rules:
                            print("\t\tRules found!!")
                            print(rules)
                            features_with_rules.append(feature)

                    if features_with_rules:
                        print("\nFeatures with rules:")

                    for feature in features_with_rules:
                        print(f"{feature}")

