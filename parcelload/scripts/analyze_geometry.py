"""
Geometry shift analysis for monthly parcel loads.

Compares old (backup) and new polygon feature classes to detect parcels
whose geometry has shifted beyond configurable thresholds.

Two metrics are computed per matched PID:
  1. Centroid distance (metres) - detects positional shifts.
  2. Relative area change (%) - detects resizing, subdivision, or consolidation.
"""

import csv
import logging
import math
import os

import arcpy

logger = logging.getLogger(__name__)


def _build_parcel_geometry_dict(feature_class, pid_field="PID"):
    """Build {PID: arcpy.Geometry} from a polygon feature class.

    When a PID maps to multiple rows (multi-part parcels stored as
    separate features), the geometries are unioned so that centroid
    and area reflect the full parcel extent.
    """

    parcel_geoms = {}

    with arcpy.da.SearchCursor(feature_class, [pid_field, "SHAPE@"]) as cursor:
        for pid, shape in cursor:
            if not pid or not shape or shape.area == 0:
                continue

            if pid in parcel_geoms:
                parcel_geoms[pid] = parcel_geoms[pid].union(shape)
            else:
                parcel_geoms[pid] = shape

    return parcel_geoms


def analyze_parcel_geometry_shift(
    old_polygons,
    new_polygons,
    distance_threshold=5.0,
    area_change_threshold=0.10,
    pid_field="PID",
):
    """Compare old and new parcel polygons to detect geometry shifts.

    For each PID present in both datasets, computes:
      - Euclidean distance between polygon centroids (metres, projected CRS).
      - Relative area change: abs(new_area - old_area) / old_area.

    Parcels exceeding either threshold are flagged.

    Parameters
    ----------
    old_polygons : str
        Path to the old (backup) polygon feature class or shapefile.
    new_polygons : str
        Path to the new polygon feature class or shapefile.
    distance_threshold : float
        Maximum acceptable centroid shift in metres.  Default 5.0.
    area_change_threshold : float
        Maximum acceptable relative area change (0.10 = 10%).  Default 0.10.
    pid_field : str
        Name of the parcel-ID field.  Default ``"PID"``.

    Returns
    -------
    dict
        ``"flagged"``  - list[dict] parcels exceeding a threshold.
        ``"added"``    - list[str]  PIDs only in the new dataset.
        ``"removed"``  - list[str]  PIDs only in the old dataset.
        ``"summary"``  - dict with aggregate counts and thresholds used.
    """

    logger.info(f"Building geometry dict from old polygons: {old_polygons}")
    old_geoms = _build_parcel_geometry_dict(old_polygons, pid_field)
    logger.info(f"  {len(old_geoms)} parcels in old dataset")

    logger.info(f"Building geometry dict from new polygons: {new_polygons}")
    new_geoms = _build_parcel_geometry_dict(new_polygons, pid_field)
    logger.info(f"  {len(new_geoms)} parcels in new dataset")

    old_pids = set(old_geoms.keys())
    new_pids = set(new_geoms.keys())

    common_pids = old_pids & new_pids
    added_pids = sorted(new_pids - old_pids)
    removed_pids = sorted(old_pids - new_pids)

    logger.info(
        f"  {len(common_pids)} common PIDs, "
        f"{len(added_pids)} added, {len(removed_pids)} removed"
    )

    flagged = []

    for pid in sorted(common_pids):
        old_geom = old_geoms[pid]
        new_geom = new_geoms[pid]

        old_centroid = old_geom.centroid
        new_centroid = new_geom.centroid

        centroid_dist = math.hypot(
            new_centroid.X - old_centroid.X,
            new_centroid.Y - old_centroid.Y,
        )

        old_area = old_geom.area
        new_area = new_geom.area

        if old_area > 0:
            area_change_pct = abs(new_area - old_area) / old_area
        else:
            area_change_pct = float("inf") if new_area > 0 else 0.0

        dist_exceeded = centroid_dist > distance_threshold
        area_exceeded = area_change_pct > area_change_threshold

        if not (dist_exceeded or area_exceeded):
            continue

        if dist_exceeded and area_exceeded:
            flag = "SHIFT+RESIZE"
        elif dist_exceeded:
            flag = "SHIFT"
        else:
            flag = "RESIZE"

        flagged.append(
            {
                "PID": pid,
                "centroid_distance_m": round(centroid_dist, 3),
                "old_area_m2": round(old_area, 2),
                "new_area_m2": round(new_area, 2),
                "area_change_pct": round(area_change_pct * 100, 2),
                "flag": flag,
            }
        )

    summary = {
        "total_old": len(old_geoms),
        "total_new": len(new_geoms),
        "common": len(common_pids),
        "added": len(added_pids),
        "removed": len(removed_pids),
        "flagged": len(flagged),
        "flagged_shift": sum(1 for f in flagged if "SHIFT" in f["flag"]),
        "flagged_resize": sum(1 for f in flagged if "RESIZE" in f["flag"]),
        "distance_threshold_m": distance_threshold,
        "area_change_threshold_pct": area_change_threshold * 100,
    }

    logger.info(
        f"Geometry shift analysis complete: {summary['flagged']} parcels flagged "
        f"({summary['flagged_shift']} shift, {summary['flagged_resize']} resize)"
    )

    return {
        "flagged": flagged,
        "added": added_pids,
        "removed": removed_pids,
        "summary": summary,
    }


def write_geometry_shift_report(results, output_csv):
    """Write flagged parcels from a geometry shift analysis to CSV.

    Parameters
    ----------
    results : dict
        Return value of :func:`analyze_parcel_geometry_shift`.
    output_csv : str
        Destination path for the CSV report.
    """

    fieldnames = [
        "PID",
        "centroid_distance_m",
        "old_area_m2",
        "new_area_m2",
        "area_change_pct",
        "flag",
    ]

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in results["flagged"]:
            writer.writerow(row)

    logger.info(f"Geometry shift report written to {output_csv} "
                f"({len(results['flagged'])} flagged parcels)")
