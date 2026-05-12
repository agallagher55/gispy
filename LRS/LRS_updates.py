import os

import arcpy
import time
import logging
import csv
import sys
import traceback

from configparser import ConfigParser
from datetime import datetime

from arcgis.features import FeatureLayer
from arcgis.gis import GIS

from HRMutils import (setupLog, send_mail, )
from LRS_reporting import export_segment_images

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

config = ConfigParser()
config.read(r"E:\HRM\Scripts\Python\config.ini")

log_file = os.path.join(
    config.get('LOGGING', 'logDir'),
    "LRS_Updates",
    f"{datetime.today().date()}_LRS_updates.log"
)

logger = setupLog(log_file)
log_server = config.get('LOGGING', 'serverName')

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # logger.info logs to console

SDEADM_RW = config.get('SDEADM_RW', 'sdeFile')
SDEADM_RO = config.get('SDEADM_RO', 'sdeFile')

LRS_DIR = r"\\msfs203.hrm.halifax.ca\GISData\Data Sharing\LRS_operational"
LRS_GDB = os.path.join(LRS_DIR, "lrs_view.gdb")

LRS_VIEW_NAME = "TRNLRS_TRN_street_VW"
SDE_DYN_SEG_FEATURE_NAME = "TRNLRS_segmented_street_events"

SDE_SPEED_LIMIT_DYN_SEG_FEATURE_NAME = "TRNLRS_segmented_speed_limit_events"
SPEED_LIMIT_NEIGHBOURHOOD_FEATURE_NAME = "TRNLRS_SpeedLimit_Neighbourhood_VW"

MTM5_SPATIAL_REFERENCE = (
    'PROJCS["NAD_1983_CSRS_2010_MTM_5_Nova_Scotia",'
    'GEOGCS["GCS_North_American_1983_CSRS_2010",'
    'DATUM["D_North_American_1983_CSRS",'
    'SPHEROID["GRS_1980",6378137.0,298.257222101]],'
    'PRIMEM["Greenwich",0.0],'
    'UNIT["Degree",0.0174532925199433]],'
    'PROJECTION["Transverse_Mercator"],'
    'PARAMETER["False_Easting",25500000.0],'
    'PARAMETER["False_Northing",0.0],'
    'PARAMETER["Central_Meridian",-64.5],'
    'PARAMETER["Scale_Factor",0.9999],'
    'PARAMETER["Latitude_Of_Origin",0.0],'
    'UNIT["Meter",1.0]]'
    ';19877400 -10001100 10000;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision'
)


class LicenseError(Exception):
    pass

class DynSegFeature:
    """Dynamic Segmentation Feature (result of overlay events GP tool)"""

    def __init__(self, sde_workspace: str=SDEADM_RW, feature_name: str=SDE_DYN_SEG_FEATURE_NAME):

        self.sde_workspace = sde_workspace
        self.feature_name = feature_name
        self.feature = os.path.join(sde_workspace, feature_name)

        self.event_tables = [
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_StreetDirection',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_StreetClass',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_AddressRange',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_PSAB',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_StreetOwnership',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_StreetStatus',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_WinterMaintenance',
        ]

        self.network_fields = "OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;GLOBALID"
        self.speed_limit_neighbourhood_event_tables = [
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_StreetClass',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_SpeedLimit',
            rf'{self.sde_workspace}\SDEADM.TRNLRS\SDEADM.E_SpeedLimit_Neighbourhood',
        ]

    def _make_query_layer(self, query: str, layer_name: str = "out_layer"):
        """Create a polyline query layer using the standard spatial reference."""
        return arcpy.MakeQueryLayer_management(
            input_database=self.sde_workspace,
            out_layer_name=layer_name,
            query=query,
            oid_fields="OBJECTID",
            shape_type="POLYLINE",
            srid="0",
            spatial_reference=MTM5_SPATIAL_REFERENCE,
            m_values="DO_NOT_INCLUDE_M_VALUES",
            z_values="DO_NOT_INCLUDE_Z_VALUES",
        )[0]

    def update_dynamic_segmentation(self):
        """
        - Update LRS view by recreating the table that the view is derived from.
        :return:
        """

        try:

            logger.info(f"Overlaying events to create '{self.feature_name}'...")
            arcpy.locref.OverlayEvents(
                in_route_features=rf"{self.sde_workspace}\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.LRSN_Route",
                event_layers=self.event_tables,
                output_dataset=self.feature,
                include_geometry="INCLUDE_GEOMETRY",
                network_fields=self.network_fields
            )
            logger.info(arcpy.GetMessages())

            logger.info(f"\tRecreated {self.feature}")

            arcpy.ChangePrivileges_management(
                in_dataset=self.feature,
                user="PUBLIC",
                View="GRANT",
            )

            return self.feature

        except arcpy.ExecuteError:
            run_error_processing(
                f"Error updating Dynamic Segmentation {self.feature_name}. Details: {str(arcpy.GetMessages(2))}"
            )


    def _update_streets(self, where_clause: str, out_feature: str):
        logger.info(f"Creating query layer with filter: '{where_clause}'")

        query = f"""
        SELECT
            e.OBJECTID,
            e.FCODE,
            e.STR_NAME,
            e.STR_TYPE,
            e.ROUTENAME AS FULL_NAME,
            e.MUN_CODE,
            e.FROM_STR,
            e.TO_STR,
            e.STR_DIR,
            e.STR_STATUS,
            e.ST_CLASS,
            e.OWN,
            e.MAINTENANCE,
            e.DATE_ACCEPT,
            e.COMMENT__2 AS STR_REM,
            e.FLAG AS FLAGS,
            e.PSAB_CODE,
            e.FDMID,
            e.SYS_DATE,
            e.ROUTE_ID,
            e.FROM_LEFT,
            e.TO_LEFT,
            e.FROM_RIGHT,
            e.TO_RIGHT,
            e.OLD_FDMID,
            e.GSA_LEFT,
            e.GSA_RIGHT,
            e.PAR_LEFT,
            e.PAR_RIGHT,
            e.STR_CODE_L,
            e.STR_CODE_R,
            e.ASSETID,
            e.ORIGIN_DATE,
            ea.MinAddDate AS ADDDATE,
            ea.MaxModDate AS MODDATE,
            e.SHAPE
        FROM {self.feature_name} e
        LEFT JOIN (
            SELECT
                FDMID,
                Min(ADDDATE) AS MinAddDate,
                MAX(MODDATE) AS MaxModDate
            FROM SDEADM.E_ADDRESSRANGE
            WHERE
                (GDB_IS_DELETE IS NULL OR GDB_IS_DELETE = 0)
            GROUP BY FDMID
        ) ea
        ON e.fdmid = ea.fdmid
        WHERE {where_clause}
        """

        query_layer = self._make_query_layer(query)

        record_count = int(arcpy.GetCount_management(query_layer)[0])
        logger.info(f"Row count: {record_count}")

        if record_count > 0:
            append_feature(query_layer, out_feature, self.sde_workspace)

    def _update_street_lanes(self, out_feature: str):

        # Lane data pulls from TRN_street. Hasn't been updated in a long time, and the geometry of the lane data isn't
        # perfect, so it causes duplicated FDMIDs and short segments if added to the dynamic segmentation

        logger.info("Creating street lanes query layer...")

        query = f"""
        SELECT
            lrs_streets.OBJECTID,
            lrs_streets.FCODE,
            lrs_streets.STR_NAME,
            lrs_streets.STR_TYPE,
            lrs_streets.FULL_NAME,
            lrs_streets.MUN_CODE,
            lrs_streets.FROM_STR,
            lrs_streets.TO_STR,
            lrs_streets.STR_DIR,
            lrs_streets.STR_STATUS,
            lrs_streets.ST_CLASS,
            lrs_streets.OWN,
            lrs_streets.MAINTENANCE,
            lrs_streets.DATE_ACCEPT,
            lrs_streets.STR_REM,
            lrs_streets.FLAGS,
            lrs_streets.PSAB_CODE,
            lrs_streets.FDMID,
            lrs_streets.ROUTE_ID,
            lrs_streets.FROM_LEFT,
            lrs_streets.TO_LEFT,
            lrs_streets.FROM_RIGHT,
            lrs_streets.TO_RIGHT,
            lrs_streets.OLD_FDMID,
            lrs_streets.GSA_LEFT,
            lrs_streets.GSA_RIGHT,
            lrs_streets.PAR_LEFT,
            lrs_streets.PAR_RIGHT,
            lrs_streets.STR_CODE_L,
            lrs_streets.STR_CODE_R,
            lrs_streets.ASSETID,
            lrs_streets.ADDDATE,
            lrs_streets.MODDATE,
            lrs_streets.SHAPE,
            LANECOUNT AS LANE
        FROM SDEADM.{LRS_VIEW_NAME} lrs_streets
        LEFT JOIN SDEADM.TRN_STREET trn_street
        ON lrs_streets.fdmid = trn_street.fdmid
        """

        query_layer = self._make_query_layer(query, layer_name="lanes_query_out_layer")

        record_count = int(arcpy.GetCount_management(query_layer)[0])
        logger.info(f"Row count: {record_count}")

        if record_count > 0:
            append_feature(query_layer, out_feature, self.sde_workspace)

        else:
            logger.info("Did not update.")
            return False

        return True

    def update_speed_limit_neighbourhood_segmentation(
            self,
            segmented_feature_name: str = SDE_SPEED_LIMIT_DYN_SEG_FEATURE_NAME    ):
        """Create a dynamic segmentation feature for speed limit neighbourhood review.

        The main street dynamic segmentation is intentionally left unchanged.
        This overlay uses only the events needed to expose speed, street class,
        and neighbourhood speed review status/effective date. If the source
        event class is named with Canadian spelling in a target database, pass
        ``neighbourhood_event_name="SDEADM.E_SpeedLimit_Neighbourhood"``.
        """

        segmented_feature = os.path.join(self.sde_workspace, segmented_feature_name)
        event_tables = self.speed_limit_neighbourhood_event_tables

        try:

            logger.info(f"Overlaying events to create '{segmented_feature_name}'...")
            arcpy.locref.OverlayEvents(
                in_route_features=rf"{self.sde_workspace}\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.LRSN_Route",
                event_layers=event_tables,
                output_dataset=segmented_feature,
                include_geometry="INCLUDE_GEOMETRY",
                network_fields=self.network_fields
            )
            logger.info(arcpy.GetMessages())

            logger.info(f"\tRecreated {segmented_feature}")

            arcpy.ChangePrivileges_management(
                in_dataset=segmented_feature,
                user="PUBLIC",
                View="GRANT",
            )

            return segmented_feature

        except arcpy.ExecuteError:
            run_error_processing(
                f"Error updating Dynamic Segmentation {segmented_feature_name}. Details: {str(arcpy.GetMessages(2))}"
            )

    def update_speed_limit_neighbourhood(
            self,
            out_feature: str = SPEED_LIMIT_NEIGHBOURHOOD_FEATURE_NAME
    ):
        """Create the publishable speed-limit neighbourhood feature.

        ``out_feature`` should point to a feature class with the target fields
        ROUTEID, STR_NAME, FULL_NAME, ST_CLASS, SPEED, REVIEW_STAT,
        DATE_EFFECTIVE, ADDDATE, ADDBY, MODDATE, and MODBY. Audit fields are
        sourced from E_SpeedLimit_Neighbourhood (the defining event for this
        view), joined on ROUTEID, mirroring how the street view pulls audit
        dates from E_AddressRange. The source is the speed-limit-specific
        segmented feature generated by
        :meth:`update_speed_limit_neighbourhood_segmentation`.
        """

        logger.info("Creating speed limit neighbourhood query layer...")

        query = f"""
        SELECT
            e.OBJECTID,
            e.ROUTEID,
            e.STR_NAME,
            e.ROUTENAME AS FULL_NAME,
            e.ST_CLASS,
            e.SPEED,
            e.REVIEW_STAT,
            e.DATE_EFFECTIVE,
            sln.MinAddDate AS ADDDATE,
            sln.AddBy      AS ADDBY,
            sln.MaxModDate AS MODDATE,
            sln.ModBy      AS MODBY,
            e.SHAPE
        FROM {SDE_SPEED_LIMIT_DYN_SEG_FEATURE_NAME} e
        LEFT JOIN (
            SELECT
                ROUTEID,
                MIN(ADDDATE) AS MinAddDate,
                MIN(ADDBY)   AS AddBy,
                MAX(MODDATE) AS MaxModDate,
                MAX(MODBY)   AS ModBy
            FROM SDEADM.E_SpeedLimit
            WHERE TODATE IS NULL
              AND (GDB_IS_DELETE IS NULL OR GDB_IS_DELETE = 0)
            GROUP BY ROUTEID
        ) sln ON e.ROUTEID = sln.ROUTEID
        WHERE e.TO_DATE IS NULL
        """

        query_layer = self._make_query_layer(query, layer_name="speed_limit_neighbourhood_query_out_layer")

        record_count = int(arcpy.GetCount_management(query_layer)[0])
        logger.info(f"Row count: {record_count}")

        if record_count > 0:
            append_feature(query_layer, out_feature, self.sde_workspace)

        else:
            logger.info("Did not update.")
            return False

        return True

    def update_lrs_streets(self, lrs_streets_feature: str):
        self._update_streets("e.TO_DATE IS NULL", lrs_streets_feature)

    def update_nscaf_streets(self, nscaf_streets_feature: str):
        self._update_streets("e.TO_DATE IS NOT NULL AND e.FROM_DATE IS NOT NULL", nscaf_streets_feature)

    def update_street_lanes(self, street_lanes_feature: str):
        self._update_street_lanes(street_lanes_feature)


def run_error_processing(error_message):

    logger.info("Handling Error...")

    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]

    pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
            str(sys.exc_info()[0]) + ": " + str(sys.exc_info()[1]) + "\n"

    logger.error(pymsg)
    logger.info(error_message)

    msgs = "GP ERRORS:\n" + arcpy.GetMessages(2) + "\n"
    logger.error(msgs)

    # send_mail(
    #     f"ERROR - LRS Updates Had Failures - Check Log File",
    #     log_server + " / LRS_Updates.py\n" + error_message,
    #     "Error updating LRS data."
    # )


def _write_csv_report(report_path: str, records: list[dict]):
    """Write a list of dicts to a CSV file."""
    with open(report_path, "w", newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def _cleanup_or_write_report(report_path: str, records: list[dict], error_label: str) -> bool:
    """Write records to report if any exist, otherwise remove stale report file.

    Returns True if records were written (i.e. errors found).
    """

    if records:
        logger.info(f"DYN SEG ERROR: {error_label}")
        _write_csv_report(report_path, records)
        return True

    else:
        if os.path.exists(report_path):
            os.remove(report_path)

        return False


def trnlrs_street_view_checks(dyn_seg_feature: str, short_segment_threshold: float) -> dict:
    """Run QA/QC checks on a dynamic segmentation feature.

    Parameters
    ----------
    dyn_seg_feature : str
        Path to the feature class containing dynamic segmentation results.
    short_segment_threshold : float
        Minimum length (in the units of ``SHAPE@LENGTH``) that a segment must
        exceed in order to pass the short segment check.

    Returns
    -------
    dict
        Dictionary containing the generated report file names, boolean flags
        indicating whether critical or warning errors were found, and a list
        of PNG image paths for null-FDMID segments (``segment_images``).

    The checks performed are:
        - duplicate ``FDMID`` values
        - null ``FDMID`` values
        - segments shorter than ``short_segment_threshold``
    """

    import pandas as pd

    null_gsa_report = "null_gsas.csv"
    duplicate_fdmids_report = "duplicate_fdmids.txt"
    null_fdmids_report = "null_fdmids.csv"
    short_segments_report = "short_segments.csv"

    critical_errors_found = False
    warning_errors_found = False
    segment_images = []

    dyn_seg_fields = [
        "ROUTE_ID", "FDMID", "SHAPE@LENGTH", "GSA_LEFT", "GSA_RIGHT",
        "ROUTENAME", "STR_NAME", "FROM_MEASURE", "TO_MEASURE",
    ]

    dyn_seg_data = [
        row for row in arcpy.da.SearchCursor(
            dyn_seg_feature,
            dyn_seg_fields,
            "TO_DATE IS NULL"
        )
    ]

    df = pd.DataFrame(dyn_seg_data, columns=dyn_seg_fields).sort_values(by=["SHAPE@LENGTH", "ROUTE_ID", "GSA_LEFT"])

    df['FDMID'] = pd.to_numeric(df['FDMID'], errors='coerce').round().astype('Int64')
    df['SHAPE@LENGTH'] = df['SHAPE@LENGTH'].round(3)

    # CRITICAL ERROR CHECKS
    # Check for null GSA
    null_gsa_df = df[df['GSA_LEFT'].isna() | df['GSA_RIGHT'].isna()]

    # Check for duplicate FDMIDs

    # Keep nullable Int64, just drop NA for duplicate logic
    non_null_fdmids = df['FDMID'].dropna()

    duplicate_fdmids = (
        non_null_fdmids[non_null_fdmids.duplicated(keep=False)]
        .unique()
        .tolist()
    )
    duplicate_fdmids.sort()  # now safe, all ints

    # Check for null FDMID records
    null_fdmid_df = df[df['FDMID'].isnull()].drop_duplicates()

    # Check for short segments
    # Filter for short segments
    short_segments_df = df[(df['SHAPE@LENGTH'] < short_segment_threshold) | (df['SHAPE@LENGTH'].isnull())]
    short_segments = short_segments_df.to_dict('records')

    # WARNING CHECKS
    # communities, overlapping ranges, blank street type, NSCAF, locators
    # TODO: Check for warnings

    if _cleanup_or_write_report(
        null_gsa_report, null_gsa_df[['ROUTE_ID']].to_dict('records') if not null_gsa_df.empty else [],
        "Null GSAs found!"
    ):
        critical_errors_found = True

    # Duplicate FDMIDs use a plain text report (one ID per line)
    if duplicate_fdmids:

        critical_errors_found = True

        logger.info("DYN SEG ERROR: Duplicate FDMIDs found!")

        with open(duplicate_fdmids_report, "w") as txt_file:
            for fdmid in duplicate_fdmids:
                txt_file.write(f"{fdmid}\n")

    else:
        if os.path.exists(duplicate_fdmids_report):
            os.remove(duplicate_fdmids_report)

    if not null_fdmid_df.empty:

        critical_errors_found = True
        logger.info("DYN SEG ERROR: Records with null FDMIDs found!")

        null_route_ids = null_fdmid_df['ROUTE_ID'].dropna().unique().tolist()

        # Enrich with centroid coordinates (separate geometry cursor)
        centroid_map = {}
        safe_ids = "', '".join(r.replace("'", "''") for r in null_route_ids)
        with arcpy.da.SearchCursor(
            dyn_seg_feature,
            ["ROUTE_ID", "SHAPE@TRUECENTROID"],
            f"TO_DATE IS NULL AND ROUTE_ID IN ('{safe_ids}')",
        ) as cur:
            for route_id, centroid in cur:
                if centroid and route_id not in centroid_map:
                    centroid_map[route_id] = (round(centroid.X, 1), round(centroid.Y, 1))

        null_fdmid_df = null_fdmid_df.copy()
        null_fdmid_df['Centroid_X'] = null_fdmid_df['ROUTE_ID'].map(
            lambda r: centroid_map.get(r, (None, None))[0]
        )
        null_fdmid_df['Centroid_Y'] = null_fdmid_df['ROUTE_ID'].map(
            lambda r: centroid_map.get(r, (None, None))[1]
        )

        report_cols = [
            'ROUTE_ID', 'ROUTENAME', 'STR_NAME',
            'FROMMEASURE', 'TOMEASURE', 'SHAPE@LENGTH',
            'GSA_LEFT', 'GSA_RIGHT',
            'Centroid_X', 'Centroid_Y',
        ]
        _write_csv_report(null_fdmids_report, null_fdmid_df[report_cols].to_dict('records'))

        segment_images = export_segment_images(
            dyn_seg_feature=dyn_seg_feature,
            null_route_ids=null_route_ids,
            output_dir=os.getcwd(),
        )

    else:
        if os.path.exists(null_fdmids_report):
            os.remove(null_fdmids_report)

    if _cleanup_or_write_report(
        short_segments_report, short_segments,
        f"Segments shorter than {short_segment_threshold}m found!"
    ):
        critical_errors_found = True

    return {
        "duplicate_fdmids_report": duplicate_fdmids_report,
        "null_fdmids_report": null_fdmids_report,
        "null_gsa_report": null_gsa_report,
        "short_segments_report": short_segments_report,
        "segment_images": segment_images,

        "critical_errors_found": critical_errors_found,
        "warning_errors_found": warning_errors_found
    }


def append_feature(input_feature, target_feature, sde_conn):

    logger.info(f"Updating '{target_feature}' from '{input_feature}'...")

    with arcpy.EnvManager(preserveGlobalIds=True, workspace=sde_conn):

        if not arcpy.Exists(target_feature):
            # First run: feature class doesn't exist yet — create it from source
            logger.info(f"'{target_feature}' does not exist — creating from source...")
            arcpy.CopyFeatures_management(input_feature, target_feature)
            logger.info(arcpy.GetMessages())
            arcpy.ChangePrivileges_management(target_feature, user="PUBLIC", View="GRANT")
            logger.info(f"Granted PUBLIC VIEW on {target_feature}")
        else:
            feature_name = arcpy.Describe(target_feature).name
            target_feature = os.path.join(sde_conn, feature_name)

            arcpy.TruncateTable_management(target_feature)
            logger.info(f"Truncated {target_feature}.")

            arcpy.Append_management(
                inputs=input_feature,
                target=target_feature,
                schema_type="NO_TEST"
            )

        return True


def update_service_tomeasures(lrsn_route_feature: str, gis_org: GIS, service_urls: list,
                              location_errors: list, measure_threshold: int, local_gdb: str):
    logger.info("Updating service tomeasures...")

    if arcpy.CheckExtension("LocationReferencing") == "Available":
        arcpy.CheckOutExtension("LocationReferencing")
        logger.info("Checked out LocationReferencing Extension")

    else:
        raise LicenseError

    # Get LRSN Route ID to_measures
    lrsn_route_lengths = {
        row[0]: row[1] for row in arcpy.da.SearchCursor(lrsn_route_feature, ["ROUTEID", 'SHAPE.STLength()'])
    }

    logger.info("Processing Event Layers...")
    for count, service_url in enumerate(service_urls, start=1):

        logger.info(f"Service URL: {service_url}")

        event_feature_layer = FeatureLayer(service_url, gis_org)
        feature_layer_name = event_feature_layer.properties.name

        logger.info(f"\n{count}/{len(service_urls)}) '{feature_layer_name}'")

        edited_features = list()

        event_tomeasure_field = "TOMEASURE"

        for location_error in location_errors:

            locerror_sql = f"LOCERROR = '{location_error}'"

            logger.info(f"LOCATION ERROR SQL: {locerror_sql}")

            if location_error == 'ROUTE LOCATION NOT FOUND':

                # Export rows to feature class
                logger.info("Exporting feature...")
                errors_fc = arcpy.ExportFeatures_conversion(
                    in_features=service_url,
                    out_features=os.path.join(local_gdb, f"{arcpy.ValidateTableName(feature_layer_name, local_gdb)}"),
                    where_clause=locerror_sql,
                )[0]
                logger.info(arcpy.GetMessages())

                errors_count = int(arcpy.GetCount_management(errors_fc)[0])

                if errors_count > 0:

                    # Update the measure field
                    logger.info("Updating MEASURE values in exported feature class...")
                    with arcpy.da.UpdateCursor(errors_fc, ["ROUTEID", "MEASURE"]) as uCursor:

                        for row in uCursor:
                            route_id = row[0]
                            current_measure = row[1]

                            update_measure = lrsn_route_lengths.get(route_id)

                            row[1] = update_measure

                            logger.info(f"Updating MEASURE from {current_measure} to {update_measure}")

                            uCursor.updateRow(row)

                    # Delete events from LRS event table
                    logger.info("Deleting events...")
                    deleted_service_features = event_feature_layer.delete_features(
                        # deletes=None,  # A comma separated string of OIDs to remove from the service.
                        where=locerror_sql,
                        return_delete_results=True
                    )

                    # TODO: Remove editor tracking from event/Delete entries for ADDBY/ADDDATE after load

                    # Append events into LRS table
                    logger.info(f"Appending Events ({errors_count})...")
                    arcpy.locref.AppendEvents(
                        in_dataset=errors_fc,
                        in_target_event=service_url,
                        load_type="ADD",
                        generate_event_ids="NO_GENERATE_EVENT_IDS",
                        generate_shapes="GENERATE_SHAPES"
                    )

                else:
                    logger.info("No errors found!")

            # Get feature list
            feature_fields = [x.get("name") for x in event_feature_layer.field_groups['fields']]

            if not "LOCERROR" in feature_fields:
                logger.info("LOCERROR field not in table...")
                continue

            feature_set = event_feature_layer.query(where=locerror_sql)
            feature_list = feature_set.features

            if feature_list:

                logger.info(f"\t{len(feature_list)} features found from filter '{locerror_sql}'.")
                logger.info(f"Checking if features are within {measure_threshold}m (threshold) of LRSN route length...")

                for feature in feature_list:

                    # COMPARE FEATURE TOMEASURE WITH LRSN TO_MEASURE
                    route_id = feature.get_value(field_name='ROUTEID')
                    to_measure = feature.get_value(field_name=event_tomeasure_field)

                    logger.info(f"Checking feature with ROUTEID: '{route_id}'")

                    # Get matching TOMEASURE from LRSN_ROUTE, using ROUTEID
                    lrsn_to_measure = lrsn_route_lengths.get(route_id)
                    update_required = None

                    logger.info(f"\tLRSN to_measure: {lrsn_to_measure}")
                    logger.info(f"\tFeature to_measure: {to_measure}")

                    if lrsn_to_measure and to_measure:
                        # check if measures are within 30m
                        measure_diff = abs(lrsn_to_measure - to_measure)
                        update_required = measure_diff < measure_threshold
                        logger.info(f"\tMeasure difference: {round(measure_diff, 2)}")

                    logger.info(f"\tUpdate required: {update_required}")

                    if update_required and location_error in (
                            # "PARTIAL MATCH FOR TO-MEASURE",
                            "PARTIAL MATCH FOR THE TO-MEASURE"
                    ):
                        logger.info(f"\tCurrent to_measure: {to_measure}")
                        logger.info(f"\t--> LRSN to_measure: {lrsn_to_measure}")

                        # Update TOMEASURE
                        feature.set_value(
                            field_name=event_tomeasure_field,
                            value=lrsn_to_measure
                        )

                        logger.info("\tFeature will be updated.")
                        edited_features.append(feature)

                if edited_features:

                    # https://developers.arcgis.com/rest/services-reference/enterprise/apply-edits/

                    logger.info("Saving edits to Feature Layer...")

                    # TODO: Get EVENTIDs
                    event_ids = [x.attributes.get('EVENTID') for x in edited_features]

                    import json
                    import requests

                    lrs_apply_edits_url = f"{event_feature_layer.url}/exts/LRServer/applyEdits"
                    # https://gisapp-int.halifax.ca/extn/rest/services/LRS_EventEditor/FeatureServer/1/applyEdits

                    # edits=[{"id":2,"updates":[{"eventId":"ABC123","attributes":{"FromMeasure":42.5,"ToDate":null}}]}]

                    edits = [
                        '''

                            {
                                # "id": < eventLayerId >,
                                # "allowMerge": < true | false >,
                                # "updates": [ < record1 >, < record2 >, ...],
                                # "mergeEvents": < record >
                            },

                            {
                              "eventId": <eventId>,  // string or number value
                              "fromDate": <fromDate>,  // date value
                              "where": "<whereClause>",
                              "attributes": {
                                "<field1>": <value1>,
                                "<field2>": <value2>,
                                ...
                              }
                            }
                        '''
                    ]

                    event_ids = [x.attributes.get('EVENTID') for x in edited_features]

                    final_edits = [{"id": count}]
                    update_edits = list()

                    for edit in edited_features:
                        structured_edit = dict()

                        # Build dict
                        structured_edit["eventid"] = edit.attributes.get('EVENTID')

                        # attributes
                        # The attributes object should contain only those attribute values that are to be updated. Attribute names are case sensitive.

                        structured_edit['attributes'] = {
                            'TOMEASURE': edit.attributes.get('TOMEASURE'),
                        }

                        update_edits.append(structured_edit)

                    final_edits['updates'] = update_edits

                    lrs_apply_edits_url = f"{lrs_services_url}?f=json&edits={edits}"

                    # token = gis._con.token

                    # payload = {
                    #     "gdbVersion": "sde.DEFAULT",  # or your branch, e.g. "GISRW01.SDEADM.QA_ALEX"
                    #     "rollbackOnFailure": True,
                    #     "edits": json.dumps({
                    #         "updates": edited_features
                    #     }),
                    #     "f": "json",
                    #     # "token": token
                    # }
                    #
                    # r = requests.post(lrs_apply_edits_url, data=payload)
                    # r.raise_for_status()

                    event_feature_layer.edit_features(updates=edited_features)

                    logger.info("\nFeature layer updated.")
                    logger.info(f"\tUpdate counts: {len(edited_features)}")

                    # Generate events
                    try:
                        logger.info("\nGenerating events...")
                        arcpy.CheckOutExtension("LocationReferencing")
                        arcpy.locref.GenerateEvents(in_event_layer=service_url)
                        # TODO: may have to re-run

                    except arcpy.ExecuteError:
                        logger.info(arcpy.GetMessages())
                        logger.info(f"Sometimes have to re-run...")

                    finally:
                        arcpy.CheckInExtension('LocationReferencing')

                else:
                    logger.info(
                        "\n\tDidn't find any features that needed editing "
                        "(features didn't meet THRESHOLD or loc error type)."
                    )

            else:
                logger.info("**No features found (using SQL query) needing an update.")


def generate_intersections(sde_branch):

    """
    - Requires location referencing extension
    - Requires branch versioned connection
    """

    logger.info("Generating intersections...")

    lrs_feature_dataset = "SDEADM.TRNLRS"
    intersection_fc = os.path.join(lrs_feature_dataset, "SDEADM.INT_RouteOnRoute")
    network_layer = os.path.join(lrs_feature_dataset, "SDEADM.LRSN_Route")

    with arcpy.EnvManager(workspace=sde_branch):

        arcpy.locref.GenerateIntersections(
            in_intersection_feature_class=intersection_fc,
            in_network_layer=network_layer,
            start_date=None,
            edited_by_current_user="ALL_USERS"
        )

        logger.info(arcpy.GetMessages())

        return True


if __name__ == "__main__":

    start_time = time.asctime(time.localtime(time.time()))
    logger.info(f"Start: {start_time}")
    logger.info("-----------------------")

    try:

        if arcpy.CheckExtension("LocationReferencing") == "Available":
            arcpy.CheckOutExtension("LocationReferencing")
            logger.info("Checked out LocationReferencing Extension.")

        else:
            raise LicenseError("Unable to checkout Location Referencing License.")

        # generate_intersections(sde_branch=r"E:\HRM\Scripts\SDE\SQL\prod_RW_sdeadm_branch.sde")

        sde_lrs_trn_streets_feature = os.path.join(SDEADM_RW, LRS_VIEW_NAME)
        sde_lrs_speed_limit_feature = os.path.join(SDEADM_RW, SPEED_LIMIT_NEIGHBOURHOOD_FEATURE_NAME)

        retired_streets_nscaf = os.path.join(SDEADM_RW, "SDEADM.TRNLRS_TRN_street_retired")
        street_lanes_feature = os.path.join(SDEADM_RW, "SDEADM.TRNLRS_TRN_street_lanes")

        dyn_seg_feature_new = DynSegFeature(SDEADM_RW, SDE_DYN_SEG_FEATURE_NAME)

        logger.info(f"Updating dynamic segmentation in '{dyn_seg_feature_new.feature_name}'...")
        dyn_seg_feature_new.update_dynamic_segmentation()

        # dyn_seg_feature_new.update_speed_limit_neighbourhood_segmentation()  # TODO: Uncomment

        ###################################################################################
        # DYN SEG Feature Checks
        ###################################################################################

        lrs_email_recipents = [
            'tr33177@halifax.ca',
            'me24191@halifax.ca',
            'coville@halifax.ca',
            'ry51347@halifax.ca',
            'ma18333@halifax.ca',
        ]

        short_segment_threshold = 3.174511  # FUNCTION VAR
        view_checks_info = trnlrs_street_view_checks(dyn_seg_feature_new.feature, short_segment_threshold)

        if view_checks_info["critical_errors_found"] or view_checks_info["warning_errors_found"]:

            reports = (
                view_checks_info['duplicate_fdmids_report'],
                view_checks_info['null_fdmids_report'],
                view_checks_info['null_gsa_report'],
                view_checks_info['short_segments_report'],
            )

            written_reports = [x for x in reports if os.path.exists(x)]
            written_reports += view_checks_info['segment_images']

            send_mail(
                to=lrs_email_recipents,
                subject="TRNLRS_street_view Errors & Warnings Report (from QA)",
                text="Uh oh, we have a small problem - attached is some information regarding some issues feeding the TRNLRS_steet_VW, for your VIEWing pleasure."
                     f"\n\t(The shortest segment threshold used was '{short_segment_threshold}')"
                     f"\nCheck out geometry information here: '{SDE_DYN_SEG_FEATURE_NAME}'"
                     "\n\nGodspeed.",
                files=written_reports,
                cc=['gallaga@halifax.ca'],
            )

            logger.error(f"Critical errors found in {SDE_DYN_SEG_FEATURE_NAME} to prevent {LRS_VIEW_NAME} from updating")

        else:

            ###################################################################################
            # Update TRNLRS_TRN_street_VW
            ###################################################################################

            street_features = {
                sde_lrs_trn_streets_feature: {"update_method": dyn_seg_feature_new.update_lrs_streets},
                street_lanes_feature: {"update_method": dyn_seg_feature_new.update_street_lanes},
                retired_streets_nscaf: {"update_method": dyn_seg_feature_new.update_nscaf_streets},
                sde_lrs_speed_limit_feature: {"update_method": dyn_seg_feature_new.update_speed_limit_neighbourhood},
            }

            for feature, feature_info in street_features.items():

                logger.info(f"Processing {feature}")

                update = feature_info.get('update_method')

                if update:

                    rw_tbl = feature
                    ro_tbl = os.path.join(SDEADM_RO, os.path.basename(feature))

                    update(rw_tbl)

                    # Manually update RO features
                    logger.info("Updating RO features (outside of replication)...")

                    # Update RO feature from RW feature
                    append_feature(rw_tbl, ro_tbl, SDEADM_RO)

    except LicenseError:
        run_error_processing(
            "Unable to checkout Location Referencing License."
        )

    except Exception:
        run_error_processing("Error updating LRS data...")

    finally:
        arcpy.CheckInExtension('LocationReferencing')
        logger.info("Checked in LocationReferencing Extension")

    # Close the Log File:
    end_time = time.asctime(time.localtime(time.time()))
    logger.info("-----------------------")
    logger.info(f"End: {end_time}")
