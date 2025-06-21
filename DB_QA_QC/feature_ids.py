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


def query_all_features(workspace: str, wildcard: str = "*", include_datasets = True):

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


def gather_assetids(workspace: str, features: list) -> dict:
    """Return mapping of feature name to asset id values and field name."""

    print("Gathering ASSETID values...")

    assetid_info = dict()

    with arcpy.EnvManager(workspace=workspace):

        for feature in features:

            fields = arcpy.ListFields(feature)
            assetid_field = None

            for field in fields:

                if field.name.upper() in ("ASSETID", "ASSET_ID"):
                    assetid_field = field.name
                    break

            if assetid_field:

                ids = {
                    row[0] for row in arcpy.da.SearchCursor(feature, [assetid_field]) if row[0] is not None
                }

                assetid_info[feature.split(".")[-1].lower()] = {
                    "feature": feature,
                    "field": assetid_field,
                    "ids": ids,
                }

    return assetid_info


def compare_assetids(info_a: dict, info_b: dict, label_a: str, label_b: str):
    """Print differences in ASSETID values between two mappings."""

    print("\nComparing ASSETID values...")

    common_features = set(info_a) & set(info_b)

    for feature in sorted(common_features):

        ids_a = info_a[feature]["ids"]
        ids_b = info_b[feature]["ids"]

        if ids_a == ids_b:

            logger.info(f"\n{feature}: ASSETID values match")
            continue

        diff_a = ids_a - ids_b
        diff_b = ids_b - ids_a

        logger.info(f"\n{feature}: mismatching ASSETID values")

        if diff_a:

            logger.info(
                f"\tPresent only in '{label_a}': {sorted(diff_a)}"
            )

        if diff_b:

            logger.info(
                f"\tPresent only in '{label_b}': {sorted(diff_b)}"
            )



if __name__ == "__main__":

    separator = 79 * "="

    check_rules = False

    rw_db = config.get("SERVER", "dev_rw")
    ro_db = config.get("SERVER", "dev_ro")

    rw_features = query_all_features(rw_db, wildcard="*AST_*")
    ro_features = query_all_features(ro_db, wildcard="*AST_*")

    rw_info = gather_assetids(rw_db, rw_features)
    ro_info = gather_assetids(ro_db, ro_features)

    compare_assetids(rw_info, ro_info, "RW", "RO")

    if check_rules:

        for db, features in [(rw_db, rw_features), (ro_db, ro_features)]:
            features_with_rules = []
            num_features = len(features)

            with arcpy.EnvManager(workspace=db):
                for idx, feature in enumerate(features, start=1):
                    print(separator)
                    print(f"\n{idx}/{num_features}) {feature}")
                    print("\tGetting rules...")

                    rules = attr_rules.get_rules(feature)

                    if rules:
                        print("\t\tRules found!!")
                        print(rules)
                        features_with_rules.append(feature)

            if features_with_rules:
                print("\nFeatures with rules:")
                for feature in features_with_rules:
                    print(feature)
