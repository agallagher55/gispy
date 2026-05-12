import logging
import os

import arcpy

logger = logging.getLogger(__name__)


def export_segment_images(
    dyn_seg_feature: str,
    null_route_ids: list,
    output_dir: str,
    image_prefix: str = "null_fdmid",
    overview_title: str = None,
) -> list:
    """Generate PNG map images for a set of flagged segments.

    Produces one overview PNG (all affected routes highlighted in red over
    nearby context streets) and one close-up PNG per affected route.

    Parameters
    ----------
    dyn_seg_feature : str
        Path to the feature class to query.
    null_route_ids : list
        ROUTE_ID values to highlight.
    output_dir : str
        Directory where PNGs are written.
    image_prefix : str
        Prefix for output filenames (e.g. ``"null_fdmid"`` or
        ``"duplicate_fdmid"``).
    overview_title : str, optional
        Title for the overview image.  Defaults to
        ``"<image_prefix> Segments — N route(s) affected"``.

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
    title = overview_title or f"{image_prefix} segments — {len(null_geoms)} route(s) affected"
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_aspect('equal')
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)
    plt.tight_layout()
    overview_path = os.path.join(output_dir, f"{image_prefix}s_overview.png")
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
        img_path = os.path.join(output_dir, f"{image_prefix}_{safe_name}.png")
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.close()
        image_files.append(img_path)
        logger.info(f"Saved segment image: {img_path}")

    return image_files
