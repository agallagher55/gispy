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


def parcel_poly_to_point(parcel_poly_reference_feature, fgdb, repair_geometry=False):

    logging.info("Running parcel_poly_to_point...")

    feature_to_point_fc = os.path.join(fgdb, f"hrm_parcel_polygon_points")
    point_multi_feature = os.path.join(fgdb, f"hrm_parcel_polygon_points_multi")

    if repair_geometry:

        logger.info("Repair Geometry...")
        arcpy.RepairGeometry_management(
            in_features=parcel_poly_reference_feature,
            delete_null="KEEP_NULL",
            validation_method="ESRI"
        )
        logger.debug(arcpy.GetMessages())

    logger.info("Feature To Point...")
    arcpy.FeatureToPoint_management(
        in_features=parcel_poly_reference_feature,
        out_feature_class=feature_to_point_fc,
        point_location="INSIDE"
    )
    logger.debug(arcpy.GetMessages())

    logger.info("Pairwise Dissolve...")
    arcpy.PairwiseDissolve_analysis(
        in_features=feature_to_point_fc,
        out_feature_class=point_multi_feature,
        dissolve_field=["PID"],
        multi_part="MULTI_PART"
    )
    logger.debug(arcpy.GetMessages())

    return feature_to_point_fc, point_multi_feature


def update_parcel_pt(rw_workspace):

    lnd_parcel_poly = os.path.join(rw_workspace, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

    lnd_parcel_point_multi_sde_rw = os.path.join(rw_workspace, "SDEADM.LND_parcel_point")
    lnd_parcel_point_single_sde_rw = os.path.join(rw_workspace, "SDEADM.LND_parcel_point_single")

    # Parcel Polygon to point feature, dissolve on PID

    local_parcel_pt_single, local_parcel_pt_multi = parcel_poly_to_point(lnd_parcel_poly, local_gdb)

    logger.info("="*50)

    # Delete rows in RW feature
    for sde_feature in lnd_parcel_point_multi_sde_rw, lnd_parcel_point_single_sde_rw:
        logger.info(f"Truncating {sde_feature}...")
        arcpy.TruncateTable_management(sde_feature)
        logger.debug(arcpy.GetMessages())

    logger.info("="*50)

    # Multi feature
    logging.info(f"Loading {lnd_parcel_point_multi_sde_rw}...")
    arcpy.Append_management(
        inputs=local_parcel_pt_multi,
        target=lnd_parcel_point_multi_sde_rw,
        schema_type="NO_TEST",
    )
    logger.debug(arcpy.GetMessages())


if __name__ == "__main__":

    local_gdb = r"T:\work\giss\monthly\202412dec\gallaga\LND_parcel_point\scripts\data.gdb"

    sde_rw = config.get("SERVER", "dev_rw")  # config.get("SERVER", "dev_rw"), config.get("SERVER", "qa_rw"), config.get("SERVER", "prod_rw")
    sde_ro = config.get("SERVER", "dev_ro")

    update_parcel_pt(sde_rw)
