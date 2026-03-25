# metadata/

Scripts for reading, reporting, and updating SDE feature class metadata at HRM.

---

## Files

| File | Purpose |
|---|---|
| `metadata.py` | Core module — `SDSFMetaData`, `get_sde_metadata()`, `update_metadata()`, `get_workspace_features()` |
| `update_sde_metadata.py` | **Run this** to update a feature's full metadata from an SDSF Excel file |
| `metadata_update.py` | Standalone script to update only the `reviseDate` for a fixed list of features |
| `__init__.py` | Re-exports public API so external callers (`parcelload/`) can use `from metadata import ...` |

---

## Quick start — update metadata from an SDSF

1. Open `update_sde_metadata.py` and set the two config variables at the top:

```python
SDSF_PATH = r"T:\work\giss\sdsf\MyFeature_SDSF.xlsx"   # path to the SDSF workbook
FEATURE   = "SDEADM.LND_ANS_communities"                # leave "" to use Dataset Name from SDSF
```

2. Uncomment the database tiers you want to push to:

```python
for dbs in [
    [config.get(run_from, "dev_rw")],
    # [config.get(run_from, "qa_rw")],
    # [config.get(run_from, "prod_rw")],
]:
```

3. Run the script from the repo root or the `metadata/` folder:

```
python metadata/update_sde_metadata.py
```

### What gets updated

| Metadata field | Source in SDSF |
|---|---|
| Title | Dataset Name |
| Description | Dataset Description |
| Summary / Abstract | Dataset Purpose |
| Tags | Dataset Tags |
| Use Limitations | Notes or Disclaimers |
| Revised Date | Today's date (auto-set) |

---

## Core module — `metadata.py`

### `SDSFMetaData(source)`
Parses the **SDSF** sheet of an Excel workbook.

```python
from metadata.metadata import SDSFMetaData

sdsf = SDSFMetaData(r"T:\...\MyFeature_SDSF.xlsx")
print(sdsf.name)         # "METADATA: LND_ANS_communities"
print(sdsf.description)  # full dataset description
print(sdsf.summary)      # dataset purpose
print(sdsf.tags)         # comma-separated tags
print(sdsf.limitations)  # notes / disclaimers
```

### `get_sde_metadata(db, feature) -> dict`
Returns a dict of current metadata for a feature:

```python
info = get_sde_metadata(db, "SDEADM.LND_ANS_communities")
# keys: FEATURE, TITLE, DESCRIPTION, DESCRIPTION_SANITIZED,
#       TAGS, SUMMARY, CREATION_DATE, PUBLISHED_DATE, REVISION_DATE
```

### `update_metadata(db, feature, update_options)`
Applies metadata changes to a feature. All keys are optional.

```python
update_metadata(db, "SDEADM.LND_ANS_communities", {
    "title": "ANS Communities",
    "description": "Full HTML description...",
    "summary": "Short purpose statement.",
    "tags": "ANS, communities, HRM",
    "access_constraints": "For internal use only.",
    "revised_date": "2024-03-01T00:00:00",
})
```

### `get_workspace_features(workspace, schema=None) -> list`
Lists all feature classes and tables in a workspace (including those inside feature datasets).

```python
features = get_workspace_features(db, schema="SDEADM")
```

---

## Dependencies

- `arcpy` (ArcGIS Pro)
- `pandas`
- `config.ini` at the repo root (standard `[SERVER]` / `[LOCAL]` keys)
