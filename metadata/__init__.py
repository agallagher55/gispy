# Re-export public API so that external callers (e.g. parcelload/scripts/main.py)
# can continue to use: from metadata import get_sde_metadata, update_metadata
from metadata.metadata import (
    strip_html_tags,
    get_xml_text,
    SDSFMetaData,
    get_sde_metadata,
    update_metadata,
    get_workspace_features,
)

__all__ = [
    "strip_html_tags",
    "get_xml_text",
    "SDSFMetaData",
    "get_sde_metadata",
    "update_metadata",
    "get_workspace_features",
]
