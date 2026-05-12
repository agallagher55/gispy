import os

import arcpy
import logging
import csv
import sys
import traceback

from os import environ, path
from configparser import ConfigParser
from datetime import datetime

from HRMutils import setupLog, send_mail

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

working_dir = os.path.dirname(sys.path[0])
scripts_dir = os.path.join(working_dir, "Scripts")
scratch_dir = os.path.join(working_dir, "Scratch")
gdb_name = "Scratch.gdb"

scratch_gdb = os.path.join(scratch_dir, gdb_name)

arcpy.CheckOutExtension("LocationReferencing")

config = ConfigParser()
config.read('config.ini')

log_file = path.join(
    os.getcwd(),
    f"{datetime.today().date()}_TRN_street_vw_creation.log"
)
logger = setupLog(log_file)
log_server = ""

console_handler = logging.StreamHandler()
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s', datefmt='%d-%b-%y %H:%M:%S'
)
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)  # logger.info logs to console

LRS_DIR = r"\\msfs203.hrm.halifax.ca\GISData\Data Sharing\LRS_operational"
LRS_GDB = os.path.join(LRS_DIR, "lrs_view.gdb")

LRS_VIEW_NAME = "TRNLRS_TRN_street_VW"

PRE_VIEW_FEATURE_NAME = "TRNLRS_segmented_street_events"

class LicenseError(Exception):
    pass


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
    #     f"ERROR - GDB Replication Had Failures - Check Log File",
    #     log_server + " / GDB_Replication.py\n" + error_message
    # )


def export_segment_images(dyn_seg_feature: str, null_route_ids: list, output_dir: str) -> list:
    """Generate PNG map images for segments with null FDMIDs.

    Produces one overview PNG (all affected routes highlighted in red over
    nearby context streets) and one close-up PNG per affected route.

    Returns a list of created image file paths, or an empty list if
    matplotlib is unavailable or no geometry is found.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.lines as mlines
    except ImportError:
        logger.warning("matplotlib not available — skipping segment image export")
        return []

    if not null_route_ids:
        return []

    route_id_set = set(null_route_ids)
    safe_ids = "', '".join(r.replace("'", "''") for r in null_route_ids)
    where_null = f"TO_DATE IS NULL AND ROUTE_ID IN ('{safe_ids}')"

    # Collect geometry for the affected segments
    null_geoms = {}  # route_id -> {"coords": [[...]], "routename": str}
    with arcpy.da.SearchCursor(
        dyn_seg_feature, ["ROUTE_ID", "ROUTENAME", "SHAPE@"], where_null
    ) as cursor:
        for route_id, routename, geom in cursor:
            if geom is None:
                continue
            coords = [
                [(pt.X, pt.Y) for pt in part if pt is not None]
                for part in geom
            ]
            coords = [c for c in coords if len(c) >= 2]
            if coords:
                null_geoms[route_id] = {
                    "coords": coords,
                    "routename": routename or route_id,
                }

    if not null_geoms:
        logger.warning("No geometry found for null FDMID segments — skipping image export")
        return []

    # Bounding box of all affected segments, used to limit context loading
    all_xs = [x for s in null_geoms.values() for part in s["coords"] for x, _ in part]
    all_ys = [y for s in null_geoms.values() for part in s["coords"] for _, y in part]
    min_x, max_x = min(all_xs), max(all_xs)
    min_y, max_y = min(all_ys), max(all_ys)
    context_buffer = 2000  # metres

    # Load nearby context segments for background reference
    context_geoms = []
    with arcpy.da.SearchCursor(
        dyn_seg_feature, ["ROUTE_ID", "SHAPE@"], "TO_DATE IS NULL"
    ) as cursor:
        for route_id, geom in cursor:
            if geom is None or route_id in route_id_set:
                continue
            ext = geom.extent
            if (
                ext.XMax < min_x - context_buffer
                or ext.XMin > max_x + context_buffer
                or ext.YMax < min_y - context_buffer
                or ext.YMin > max_y + context_buffer
            ):
                continue
            for part in geom:
                coords = [(pt.X, pt.Y) for pt in part if pt is not None]
                if len(coords) >= 2:
                    context_geoms.append(coords)

    image_files = []

    # --- Overview: all null FDMID segments ---
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.set_facecolor('#f5f5f5')
    for coords in context_geoms:
        xs, ys = zip(*coords)
        ax.plot(xs, ys, color='#cccccc', linewidth=0.5, zorder=1)
    for info in null_geoms.values():
        for part_coords in info["coords"]:
            xs, ys = zip(*part_coords)
            ax.plot(xs, ys, color='red', linewidth=2.5, zorder=2)
    null_handle = mlines.Line2D([], [], color='red', linewidth=2.5, label='Null FDMID segment')
    ax.legend(handles=[null_handle], loc='lower right', fontsize=8)
    ax.set_title(
        f"Null FDMID Segments — {len(null_geoms)} route(s) affected",
        fontsize=12, fontweight='bold',
    )
    ax.set_aspect('equal')
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    plt.tight_layout()
    overview_path = os.path.join(output_dir, "null_fdmids_overview.png")
    plt.savefig(overview_path, dpi=150, bbox_inches='tight')
    plt.close()
    image_files.append(overview_path)
    logger.info(f"Saved overview image: {overview_path}")

    # --- Per-segment close-ups ---
    pad = 500  # metres around centroid
    for route_id, info in null_geoms.items():
        seg_xs = [x for part in info["coords"] for x, _ in part]
        seg_ys = [y for part in info["coords"] for _, y in part]
        cx = sum(seg_xs) / len(seg_xs)
        cy = sum(seg_ys) / len(seg_ys)

        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_facecolor('#f5f5f5')
        for coords in context_geoms:
            xs, ys = zip(*coords)
            if any(cx - pad <= x <= cx + pad and cy - pad <= y <= cy + pad for x, y in zip(xs, ys)):
                ax.plot(xs, ys, color='#cccccc', linewidth=0.8, zorder=1)
        for part_coords in info["coords"]:
            xs, ys = zip(*part_coords)
            ax.plot(xs, ys, color='red', linewidth=3, zorder=2)
        ax.set_xlim(cx - pad, cx + pad)
        ax.set_ylim(cy - pad, cy + pad)
        ax.set_title(
            f"Route: {route_id}  |  {info['routename']}",
            fontsize=10, fontweight='bold',
        )
        ax.set_aspect('equal')
        ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
        ax.annotate(
            f"Centroid (MTM5): ({cx:.1f}, {cy:.1f})",
            xy=(0.02, 0.02), xycoords='axes fraction',
            fontsize=7, color='#555555',
        )
        plt.tight_layout()
        safe_name = "".join(c if c.isalnum() or c in "_-" else "_" for c in route_id)
        img_path = os.path.join(output_dir, f"null_fdmid_{safe_name}.png")
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.close()
        image_files.append(img_path)
        logger.info(f"Saved segment image: {img_path}")

    return image_files


def trnlrs_street_view_checks(dyn_seg_feature: str, short_segment_threshold: float, scratch_gdb: str = None) -> dict:
    """Run QA/QC checks on a dynamic segmentation feature.

    Parameters
    ----------
    dyn_seg_feature : str
        Path to the feature class containing dynamic segmentation results.
    short_segment_threshold : float
        Minimum length (in the units of ``SHAPE@LENGTH``) that a segment must
        exceed in order to pass the short segment check.
    scratch_gdb : str, optional
        Path to a scratch file geodatabase.  When supplied, null-FDMID segments
        are exported there as a standalone feature class so the reviewer can
        load them directly in ArcGIS Pro.

    Returns
    -------
    dict
        Dictionary containing the generated report file names, boolean flags
        indicating whether critical or warning errors were found, a list of
        PNG image paths for null-FDMID segments, and an optional GDB layer path.

    The checks performed are:
        - duplicate ``FDMID`` values
        - null ``FDMID`` values
        - segments shorter than ``short_segment_threshold``
    """

    import pandas as pd

    null_gsa_report = f"null_gsas.csv"
    duplicate_fdmids_report = f"duplicate_fdmids.txt"
    null_fdmids_report = f"null_fdmids.csv"
    short_segments_report = f"short_segments.csv"

    critical_errors_found = False
    warning_errors_found = False
    segment_images = []
    null_fdmid_layer = None

    dyn_seg_fields = [
        "ROUTE_ID", "FDMID", "SHAPE@LENGTH",
        "GSA_LEFT", "GSA_RIGHT",
        "ROUTENAME", "STR_NAME", "FROMMEASURE", "TOMEASURE",
    ]

    dyn_seg_data = [
        row for row in arcpy.da.SearchCursor(
            dyn_seg_feature,
            dyn_seg_fields, "TO_DATE IS NULL"
        )
    ]

    df = pd.DataFrame(dyn_seg_data, columns=dyn_seg_fields).sort_values(by=["SHAPE@LENGTH", "ROUTE_ID", "GSA_LEFT"])
    df['FDMID'] = df['FDMID'].round().astype('Int64')
    df['SHAPE@LENGTH'] = df['SHAPE@LENGTH'].round(3)

    # CRITICAL ERROR CHECKS
    # Check for null GSA
    null_gsa_df = df[(df['GSA_LEFT'].isnull()) | df['GSA_RIGHT'].isnull()]

    # Check for duplicate FDMIDs
    duplicate_fdmids = sorted(df[df.duplicated(subset=['FDMID'], keep=False)]['FDMID'].unique().tolist())

    # Check for null FDMID records
    null_fdmid_df = df[df['FDMID'].isnull()]

    # Check for short segments
    # Filter for short segments
    short_segments_df = df[(df['SHAPE@LENGTH'] < short_segment_threshold) | (df['SHAPE@LENGTH'].isnull())]
    short_segments = short_segments_df.to_dict('records')

    # WARNING CHECKS
    # communities, overlapping ranges, blank street type, NSCAF, locators
    # TODO: Check for warnings

    if not null_gsa_df.empty:

        critical_errors_found = True

        logger.info("Null GSAs found!")

        null_gsa_records = null_gsa_df[['ROUTE_ID']].to_dict('records')

        # Write output txt file
        try:

            with open(null_gsa_report, "w", newline='') as csv_file:
                fieldnames = null_gsa_records[0].keys()  # grab your column order
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                writer.writeheader()  # write column headers
                writer.writerows(null_gsa_records)  # write all rows at once

        except OSError as exc:
            logger.error(f"Failed to write duplicate FDMIDs report: {exc}")

    if duplicate_fdmids:

        critical_errors_found = True

        logger.info("Duplicate FDMIDs found!")

        # Write output txt file
        try:

            with open(duplicate_fdmids_report, "w") as txt_file:
                for fdmid in duplicate_fdmids:
                    txt_file.write(f"{fdmid}\n")

        except OSError as exc:
            logger.error(f"Failed to write duplicate FDMIDs report: {exc}")

    if not null_fdmid_df.empty:
        critical_errors_found = True

        logger.info("Records with null FDMIDs found!")

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
        null_fdmid_records = null_fdmid_df[report_cols].to_dict('records')

        try:
            with open(null_fdmids_report, "w", newline='') as csv_file:
                fieldnames = null_fdmid_records[0].keys()
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(null_fdmid_records)
        except OSError as exc:
            logger.error(f"Failed to write null FDMIDs report: {exc}")

        # Export null FDMID segments to GDB for direct review in ArcGIS Pro
        if scratch_gdb:
            try:
                null_fdmid_layer = os.path.join(scratch_gdb, "null_fdmid_segments")
                safe_ids_where = "', '".join(r.replace("'", "''") for r in null_route_ids)
                arcpy.conversion.ExportFeatures(
                    in_features=dyn_seg_feature,
                    out_features=null_fdmid_layer,
                    where_clause=f"TO_DATE IS NULL AND ROUTE_ID IN ('{safe_ids_where}')",
                )
                logger.info(f"Exported null FDMID segments to: {null_fdmid_layer}")
            except (arcpy.ExecuteError, OSError) as exc:
                logger.error(f"Failed to export null FDMID segments to GDB: {exc}")
                null_fdmid_layer = None

        # Generate segment images
        segment_images = export_segment_images(
            dyn_seg_feature=dyn_seg_feature,
            null_route_ids=null_route_ids,
            output_dir=os.getcwd(),
        )

    if short_segments:

        critical_errors_found = True

        logger.info(f"Segments shorter than {short_segment_threshold}m found!")

        # write output csv
        try:

            with open(short_segments_report, "w", newline='') as csv_file:
                fieldnames = short_segments[0].keys()  # grab your column order
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                writer.writeheader()  # write column headers
                writer.writerows(short_segments)  # write all rows at once

        except OSError as exc:
            logger.error(f"Failed to write short segments report: {exc}")

    return {
        "duplicate_fdmids_report": duplicate_fdmids_report,
        "null_fdmids_report": null_fdmids_report,
        "null_gsa_report": null_gsa_report,
        "short_segments_report": short_segments_report,
        "segment_images": segment_images,
        "null_fdmid_layer": null_fdmid_layer,

        "critical_errors_found": critical_errors_found,
        "warning_errors_found": warning_errors_found
    }


def update_lrs_dynamic_segmentation(out_db: str, reference_db:str, segmented_feature_name: str = "TRNLRS_segmented_street_events"):
    """
    - Update LRS view by recreating the table that the view is derived from.

    :param segmented_feature_name:
    :return:
    """

    event_tables = [
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetDirection',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetClass',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_AddressRange',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_PSAB',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetOwnership',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_StreetStatus',
        rf'{reference_db}\SDEADM.TRNLRS\SDEADM.E_WinterMaintenance',  # NEW
    ]

    network_fields = "OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;GLOBALID"

    if not arcpy.Exists(out_db):
        arcpy.CreateFileGDB_management(
            out_folder_path=os.path.dirname(out_db),
            out_name=os.path.basename(out_db),
        )

    overlay_output_feature = os.path.join(out_db, segmented_feature_name)

    try:

        if arcpy.CheckExtension("LocationReferencing") == "Available":
            arcpy.CheckOutExtension("LocationReferencing")
            logger.info("Checked out LocationReferencing Extension")

        else:
            raise LicenseError

        logger.info(f"Overlaying events to create '{segmented_feature_name}'...")
        arcpy.locref.OverlayEvents(
            in_route_features=rf"{reference_db}\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.LRSN_Route",
            event_layers=event_tables,
            output_dataset=overlay_output_feature,
            include_geometry="INCLUDE_GEOMETRY",
            network_fields=network_fields
        )
        logger.info(arcpy.GetMessages())

        logger.info(f"Recreated {overlay_output_feature}")

        if out_db.upper().endswith(".SDE"):
            arcpy.ChangePrivileges_management(
                in_dataset=overlay_output_feature,
                user="PUBLIC",
                View="GRANT",
            )

        return overlay_output_feature

    except arcpy.ExecuteError:
        run_error_processing(
            f"Error updating Dynamic Segmentation {segmented_feature_name}. Details: {str(arcpy.GetMessages(2))}"
        )

    except LicenseError:
        run_error_processing(
            f"Error updating Dynamic Segmentation {segmented_feature_name}. \n"
            f"Unable to checkout Location Referencing License."
        )

    finally:
        arcpy.CheckInExtension('LocationReferencing')
        logger.info("Checked in LocationReferencing Extension")


if __name__ == "__main__":

    PC_NAME = environ['COMPUTERNAME']
    run_from = "SERVER" if "APP" in PC_NAME else "LOCAL"

    logger.info(f"PC Name: '{PC_NAME}'\tRunning from: '{run_from}'...")

    output_geodatabase = r"T:\work\giss\monthly\202404apr\gallaga\LRS_TRN_street\New File Geodatabase.gdb"

    arcpy.CheckOutExtension("LocationReferencing")

    VW_DEFINITION = f"SELECT     OBJECTID, SHAPE,  FCODE,  STR_NAME,  STR_TYPE, ROUTENAME,  MUN_CODE, MIX_FULL,  FROM_STR,  TO_STR,  STR_DIR,  STR_STATUS, ST_CLASS,  OWN, DATE_ACCEPT,  COMMENT__2 AS STR_REM, FLAG, PSAB_CODE,  FDMID,  ROUTE_ID,  FROM_LEFT,  TO_LEFT,  FROM_RIGHT,  TO_RIGHT,  OLD_FDMID,  GSA_LEFT,  GSA_RIGHT,  PAR_LEFT,  PAR_RIGHT,  STR_CODE_L,  STR_CODE_R,  ASSETID, LANE, MAINTENANCE FROM {PRE_VIEW_FEATURE_NAME} WHERE to_date IS NULL"

    for dbs in [
        # [
        #     config.get("SERVER", "dev_rw"),
        # ],
        [
            config.get("SERVER", "prod_rw"),
        ],
    ]:

        if dbs:
            logger.info(f"Processing dbs: {', '.join(dbs)}...")

            for workspace in dbs:
                logger.info(f"DATABASE: {workspace}")

                with (((arcpy.EnvManager(workspace=workspace)))):

                    sde_dyn_seg_feature = os.path.join(workspace, "SDEADM.TRNLRS_segmented_street_events")

                    # Create new dyn seg, not feeding view

                    # pre_dyn_seg_feature = update_lrs_dynamic_segmentation(out_db=LRS_GDB, segmented_feature_name=os.path.basename("TRNLRS_segmented_street_events"))
                    pre_dyn_seg_feature = update_lrs_dynamic_segmentation(
                        out_db=scratch_gdb,
                        reference_db=workspace,
                        segmented_feature_name=os.path.basename("TRNLRS_segmented_street_events")
                    )

                    lrs_email_recipents = ['tr33177@halifax.ca', 'me24191@halifax.ca']
                    short_segment_threshold = 3.174511  # FUNCTION VAR
                    view_checks_info = trnlrs_street_view_checks(
                        pre_dyn_seg_feature, short_segment_threshold, scratch_gdb=scratch_gdb
                    )

                    if view_checks_info["critical_errors_found"] or view_checks_info["warning_errors_found"]:

                        reports = (
                            view_checks_info['duplicate_fdmids_report'], view_checks_info['null_fdmids_report'],
                            view_checks_info['null_gsa_report'], view_checks_info['short_segments_report']
                        )
                        written_reports = [x for x in reports if os.path.exists(x)]
                        written_reports += view_checks_info['segment_images']

                        null_fdmid_layer = view_checks_info['null_fdmid_layer']
                        gdb_note = (
                            f"\nNull FDMID segments exported to GDB for review: '{null_fdmid_layer}'"
                            if null_fdmid_layer else ""
                        )

                        # TODO: Skip weekends
                        # send_mail(
                        #     to=lrs_email_recipents,
                        #     subject="TRNLRS_street_view Errors & Warnings Report (from PROD)",
                        #     text="Uh oh, we have a small problem, friends - attached is some information regarding some issues feeding the TRNLRS_steet_VW, for your VIEWing pleasure."
                        #          f"\n\t(The shortest segment threshold used was '{short_segment_threshold}')"
                        #          f"\nCheck out geometry information here: '{LRS_GDB}'"
                        #          f"{gdb_note}"
                        #          "\nBreathe, think, review, and keep up the good work."
                        #          "\n\nGodspeed.",
                        #     files=written_reports,
                        #     cc=['gallaga@halifax.ca'],
                        # )

                    else:
                        # Truncate and load
                        logger.info(f"Truncating {sde_dyn_seg_feature}...")
                        arcpy.TruncateTable_management(sde_dyn_seg_feature)

                        logger.info(f"Loading {sde_dyn_seg_feature}...")
                        arcpy.Append_management(
                            inputs=pre_dyn_seg_feature,
                            target=sde_dyn_seg_feature,
                            schema_type="NO_TEST",
                        )

    # arcpy.CheckInExtension('LocationReferencing')
