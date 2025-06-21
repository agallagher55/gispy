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


def query_all_features(workspace: str, wildcard: str = "*", include_datasets=True):
    print(f"\nQuerying all {wildcard} features in '{workspace}'...")

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

            print(f"\t{feature}")

            fields = arcpy.ListFields(feature)
            assetid_field = None

            for field in fields:

                if field.name.upper() in ("ASSETID", "ASSET_ID"):
                    assetid_field = field.name
                    break

            if assetid_field:
                ids = {
                    row[0] for row in arcpy.da.SearchCursor(feature, [assetid_field])
                }

                assetid_info[feature.split(".")[-1].lower()] = {
                    "feature": feature,
                    "field": assetid_field,
                    "ids": ids,
                }

    return assetid_info


def compare_assetids(info_a: dict, info_b: dict, label_a: str, label_b: str) -> dict:
    """Compare ASSETID values between two mappings.

    Parameters
    ----------
    info_a, info_b : dict
        Output from :func:`gather_assetids` for each workspace.
    label_a, label_b : str
        Friendly labels for the two workspaces used in log messages.

    Returns
    -------
    dict
        Mapping of feature name to dictionaries describing any mismatching
        ASSETID values. Only features present in both workspaces are compared
        and returned. The dictionary is empty when all common features match.
    """

    mismatching = {}

    common_features = set(info_a) & set(info_b)
    only_a = set(info_a) - set(info_b)
    only_b = set(info_b) - set(info_a)

    for name in sorted(only_a):
        logger.info(f"{name}: only present in {label_a}")

    for name in sorted(only_b):
        logger.info(f"{name}: only present in {label_b}")

    for name in sorted(common_features):

        ids_a = info_a[name]["ids"]
        ids_b = info_b[name]["ids"]

        if ids_a == ids_b:
            logger.info(f"{name}: ASSETID values match")
            continue

        diff_a = ids_a - ids_b
        diff_b = ids_b - ids_a

        logger.info(f"{name}: mismatching ASSETID values")

        if diff_a:
            logger.info(
                f"Present only in {label_a}: {sorted(diff_a)[:10]}"
                f"{'...' if len(diff_a) > 10 else ''}"
            )

        if diff_b:
            logger.info(
                f"Present only in {label_b}: {sorted(diff_b)[:10]}"
                f"{'...' if len(diff_b) > 10 else ''}"
            )

        mismatching[name] = {label_a: diff_a, label_b: diff_b}

    return mismatching


def sync_ro_feature(rw_feature: str, ro_feature: str) -> None:
    """Truncate the RO feature and load it from the RW feature.

    Parameters
    ----------
    rw_feature : str
        Full path to the source feature in the read-write database.
    ro_feature : str
        Full path to the target feature in the read-only database.
    """

    logger.info(f"Syncing RO feature '{ro_feature}' from '{rw_feature}'")

    try:

        with arcpy.EnvManager(preserveGlobalIds=True):

            logger.debug(f"Truncating {ro_feature}...")
            arcpy.TruncateTable_management(ro_feature)
            logger.debug(arcpy.GetMessages())

            logger.debug(f"Appending {rw_feature} --> {ro_feature}...")
            arcpy.Append_management(rw_feature, ro_feature, "NO_TEST")
            logger.debug(arcpy.GetMessages())

    except arcpy.ExecuteError:
        logger.error(arcpy.GetMessages(2))

    except Exception as ex:
        logger.error(str(ex))


if __name__ == "__main__":

    separator = 79 * "="

    check_rules = False

    rw_db = config.get("SERVER", "dev_rw")
    ro_db = config.get("SERVER", "dev_ro")

    rw_features = query_all_features(rw_db, wildcard="*SDEADM.AST*")
    ro_features = query_all_features(ro_db, wildcard="*SDEADM.AST*")

    rw_info = gather_assetids(rw_db, rw_features)
    ro_info = gather_assetids(ro_db, ro_features)

    mismatching = compare_assetids(rw_info, ro_info, "RW", "RO")

    for name, diff in mismatching.items():

        rw_feature = rw_info[name]["feature"]
        ro_feature = ro_info[name]["feature"]
        sync_ro_feature(os.path.join(rw_db, rw_feature), os.path.join(ro_db, ro_feature))

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
