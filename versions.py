"""
versions.py - Inspect ArcSDE traditional versioning state: list versions and
flag ones that may still hold unreconciled edits.

Functions
---------
list_versions       Every version in a workspace, flattened out of the
                    parent/child tree (arcpy.da.ListVersions).
versions_with_edits Non-DEFAULT versions whose modifiedDate is after their
                    createdDate, i.e. edited at least once since creation.

Notes
-----
ArcSDE traditional versioning tracks edits per *version*, not per feature
class or table, and arcpy doesn't expose a per-dataset edit list (neither
does the Administer pane in ArcGIS Pro). So a version flagged here has been
edited *since it was created*, which is a candidate worth checking, not
proof it touched any one feature class you care about.

This is meant to be run before an operation that requires a versioned
dataset to be free of outstanding edits, e.g. arcpy.UnregisterAsVersioned_management,
which refuses outright with ERROR 000101 ("The dataset ... contains edits
to some versions") if any non-DEFAULT version still holds edits. Reconcile
(and post, if the edits should be kept) or delete each flagged version in
ArcGIS Pro before retrying — this module only reports, it never reconciles,
posts, or deletes a version, since that decision needs a person to look at
what's actually in it.

Logging: this module does not configure its own handlers. It uses a
placeholder logger (logging.getLogger(__name__)) that the importing script
should overwrite with its own configured logger, e.g.:

    import versions
    versions.logger = logger
"""

import logging

import arcpy

logger = logging.getLogger(__name__)


def _flatten(version_list):
    flat = []

    for version in version_list:
        flat.append(version)

        if version.children:
            flat.extend(_flatten(version.children))

    return flat


def list_versions(workspace):
    """Return every version in a workspace as a flat list.

    arcpy.da.ListVersions returns top-level versions with their children
    nested under `.children`; this flattens that tree since a version's
    place in the parent/child hierarchy doesn't matter for finding edits.

    Args:
        workspace (str): Path to an SDE connection file.

    Returns:
        list[arcpy.da.Version]: name, parentVersion, createdDate,
            modifiedDate, description, isPublic, access, children.
    """
    logger.info(f"Listing versions for: {workspace}")

    all_versions = _flatten(arcpy.da.ListVersions(workspace))

    logger.info(f"  {len(all_versions)} version(s) found.")
    return all_versions


def versions_with_edits(workspace, include_default=False):
    """Return non-DEFAULT versions that have been edited since creation.

    Args:
        workspace (str): Path to an SDE connection file.
        include_default (bool): Include the DEFAULT version in results.
            Defaults to False since DEFAULT is never a blocker for
            UnregisterAsVersioned or a reconcile/post workflow.

    Returns:
        list[dict]: name, parent_version, created_date, modified_date,
            description, access, for each flagged version.
    """
    flagged = []

    for version in list_versions(workspace):
        is_default = version.name.split(".")[-1].upper() == "DEFAULT"

        if is_default and not include_default:
            continue

        if version.modifiedDate and version.createdDate and version.modifiedDate > version.createdDate:
            flagged.append({
                "name": version.name,
                "parent_version": version.parentVersion,
                "created_date": version.createdDate,
                "modified_date": version.modifiedDate,
                "description": version.description,
                "access": version.access,
            })

    if flagged:
        logger.warning(f"{len(flagged)} version(s) edited since creation:")
        for row in flagged:
            logger.warning(
                f"  {row['name']}  parent={row['parent_version']}"
                f"  modified={row['modified_date']}  access={row['access']}"
            )
    else:
        logger.info("No versions edited since creation found.")

    return flagged


if __name__ == "__main__":
    from configparser import ConfigParser

    config = ConfigParser()
    config.read("config.ini")

    SDE_RW = config.get("SERVER", "qa_rw")

    edited_versions = versions_with_edits(SDE_RW)

    if edited_versions:
        print(f"\nVersion(s) to check before unregistering/reconciling ({len(edited_versions)}):")
        for v in edited_versions:
            print(
                f"  {v['name']}  parent={v['parent_version']}"
                f"  modified={v['modified_date']}  access={v['access']}"
            )
    else:
        print("\nNo versions edited since creation, nothing to reconcile.")
