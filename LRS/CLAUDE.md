# LRS — Location Referencing System

ArcGIS Location Referencing (ArcGIS Pro 3.3.5) for Halifax Regional Municipality street network.
Requires **Location Referencing Extension** (`arcpy.CheckOutExtension("LocationReferencing")`).

---

## Architecture Overview

The LRS stores linear asset data (pavement condition, address ranges, street attributes, etc.)
as **events** measured along **routes** rather than as standalone geometries.

```
SDEADM.TRNLRS (Feature Dataset)
├── LRS Schema
│   ├── Calibration Point
│   ├── Centerline
│   ├── Centerline Sequence
│   └── Redline
└── LRSN_Route  ← the network all events are registered against
    ├── E_AddressRange
    ├── E_BusRoute
    ├── E_CurbCondition2014 / 2016 / 2018 / 2021
    ├── E_District
    ├── E_HospitalRoute
    ├── E_IntersectingStreets
    ├── E_Landmark
    ├── E_Lane
    ├── E_PavementDistress2016 / 2018 / 2020 / 2022 / 2024
    ├── E_PavementImages
    ├── E_PavementProjects
    ├── E_PavementRoughness2016 / 2018 / 2020 / 2022 / 2024
    ├── E_PavementSurface
    ├── E_PSAB
    ├── E_StreetClass
    ├── E_StreetDirection
    ├── E_StreetOwnership
    ├── E_StreetStatus
    ├── E_WinterMaintenance
    └── INT_RouteOnRoute  (intersections)
```

All event feature classes live inside `SDEADM.TRNLRS` and are **branch versioned**.

---

## Standard Event Fields

Every event table has this base schema (managed by ArcGIS LRS):

| Field | Type | Notes |
|---|---|---|
| `OBJECTID` | OID | Auto |
| `EVENTID` | String | Unique event identifier (GUID-like) |
| `ROUTEID` | String | FK → `LRSN_Route.ROUTEID` |
| `FROMDATE` | Date | Temporal start; NULL = beginning of time |
| `TODATE` | Date | Temporal end; **NULL = currently active** |
| `FROMMEASURE` | Double | Start measure along route (metres) |
| `TOMEASURE` | Double | End measure along route (metres) |
| `LOCERROR` | String | ArcGIS-managed location error flag |
| `ADDBY` / `ADDDATE` | String/Date | Editor tracking (UTC) |
| `MODBY` / `MODDATE` | String/Date | Editor tracking (UTC) |
| `GLOBALID` | GUID | Required for replication |
| `SHAPE` | Polyline M | Geometry derived from measures |

`TODATE IS NULL` → active/current record. `TODATE IS NOT NULL` → retired/historical.

---

## Key Identifiers

| Identifier | Description |
|---|---|
| `ROUTEID` | Unique ID of a route in `LRSN_Route` |
| `ROUTENAME` | Human-readable street name |
| `FDMID` | Facility Data Model ID — links dynamic segmentation back to street segments |
| `GSA_LEFT` / `GSA_RIGHT` | Geographic Service Area on each side of the street |

---

## Spatial Reference

**NAD_1983_CSRS_2010_MTM_5_Nova_Scotia** (MTM Zone 5, EPSG-like).
All geometries, query layers, and feature classes must use this projection.
The WKT string is stored as `MTM5_SPATIAL_REFERENCE` in `LRS_Updates.py`.

---

## SDE Connections

```
SDEADM_RW   prod_RW_sdeadm_branch.sde   Branch-versioned read-write
SDEADM_RO   prod_RO_sdeadm.sde          Read-only (outside replication)
```

- Always use **branch-versioned** connections when editing events or running `locref` GP tools.
- `GenerateIntersections` requires a branch-versioned connection.
- After updating RW features, manually sync the RO connection with `append_feature()`.

---

## Street Network Dataset — How It's Built

The main street network view is assembled from the LRS via **dynamic segmentation** (overlay).
The pipeline runs on a schedule:

```
LRSN_Route + 7 event tables
        │
        ▼ arcpy.locref.OverlayEvents
TRNLRS_segmented_street_events   ← intermediate flat feature class
        │
        ├─ QA checks pass?
        │       ├── NO  → email report, abort
        │       └── YES ▼
        ├── TRNLRS_TRN_street_VW          (active streets, TO_DATE IS NULL)
        ├── TRNLRS_TRN_street_retired     (NSCAF retired, TO_DATE IS NOT NULL)
        └── TRNLRS_TRN_street_lanes       (joined to TRN_street for LANECOUNT)
```

### Event tables overlaid for the street view

```python
event_tables = [
    "SDEADM.TRNLRS\SDEADM.E_StreetDirection",
    "SDEADM.TRNLRS\SDEADM.E_StreetClass",
    "SDEADM.TRNLRS\SDEADM.E_AddressRange",
    "SDEADM.TRNLRS\SDEADM.E_PSAB",
    "SDEADM.TRNLRS\SDEADM.E_StreetOwnership",
    "SDEADM.TRNLRS\SDEADM.E_StreetStatus",
    "SDEADM.TRNLRS\SDEADM.E_WinterMaintenance",
]

network_fields = "OBJECTID;FROMDATE;TODATE;ROUTEID;ROUTENAME;STR_NAME;STR_TYPE;MUN_CODE;GLOBALID"
```

### `SDEADM.TRNLRS_trn_street_retired_VW`

A database view used by **`NSCAF_update.py`** to expose retired street segments — rows from
`TRNLRS_segmented_street_events` where `TO_DATE IS NOT NULL` (i.e. the segment has been retired
from the LRS) but that no longer appear in the active street view `TRNLRS_TRN_STREET_VW`.

**Definition:**

```sql
CREATE VIEW TRNLRS_trn_street_retired_VW AS
SELECT
    e.OBJECTID,
    e.FCODE,
    e.STR_NAME,
    e.STR_TYPE,
    e.ROUTENAME        AS FULL_NAME,
    e.MUN_CODE,
    e.FROM_STR,
    e.TO_STR,
    e.STR_DIR,
    e.STR_STATUS,
    e.ST_CLASS,
    e.OWN,
    e.MAINTENANCE,
    e.DATE_ACCEPT,
    e.COMMENT__2       AS STR_REM,
    e.FLAG             AS FLAGS,
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
    ea.MinAddDate      AS ADDDATE,
    ea.MaxModDate      AS MODDATE,
    e.SHAPE
FROM sdeadm.TRNLRS_segmented_street_events e
LEFT JOIN (
    SELECT
        ASSETID,
        MIN(ADDDATE) AS MinAddDate,
        MAX(MODDATE) AS MaxModDate
    FROM SDEADM.E_ADDRESSRANGE
    WHERE TODATE IS NULL
      AND (GDB_IS_DELETE IS NULL OR GDB_IS_DELETE = 0)
    GROUP BY ASSETID
) ea ON e.ASSETID = ea.ASSETID
WHERE e.TO_DATE   IS NOT NULL
  AND e.FROM_DATE IS NOT NULL
  AND e.FDMID     IS NOT NULL
  AND e.ST_CLASS  IS NOT NULL
  AND e.FROM_STR  IS NOT NULL
  AND e.TO_STR    IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM SDEADM.TRNLRS_TRN_STREET_VW v
      WHERE v.FDMID = e.FDMID
  );
```

**Key logic:**
- Joins `TRNLRS_segmented_street_events` (retired rows, `TO_DATE IS NOT NULL`) against
  `E_ADDRESSRANGE` to pull `ADDDATE` / `MODDATE`.
- The `NOT EXISTS` sub-select excludes any `FDMID` that is still present in the active street
  view (`TRNLRS_TRN_STREET_VW`), so only truly-retired segments appear.
- All mandatory attribute filters (`FDMID`, `ST_CLASS`, `FROM_STR`, `TO_STR`) mirror the
  completeness requirements enforced by the QA checks below.

---

### QA checks before updating the view (`trnlrs_street_view_checks`)

All four are **critical** — any failure blocks the view update and sends a report email.

| Check | Report file |
|---|---|
| Null `GSA_LEFT` or `GSA_RIGHT` | `null_gsas.csv` |
| Duplicate `FDMID` values | `duplicate_fdmids.txt` |
| Null `FDMID` values | `null_fdmids.csv` |
| Segments < 3.174511 m | `short_segments.csv` |

---

## Scripts in This Directory

| Script | Purpose |
|---|---|
| `1_create_events.py` | Create a new event table from an Excel request form |
| `events.py` | `LrsEventForm` class and `get_lrs_events()` utility |
| `event_behaviours.py` | Bulk-update event behaviour rules across features |
| `forms.py` | Older standalone version of `LrsEventForm` |
| `lrs_updates.py` | Older dynamic segmentation update + QA (single-run script) |
| `measure_updates.py` | Fix `LOCERROR` issues in Portal event layers via ArcGIS API |

---

## Creating a New Event Table (`1_create_events.py`)

Workflow triggered by an Excel "New Event Request" form (one per event type, stored in
`T:\work\giss\monthly\YYYYMM*\gallaga\<EventName>\`).

```
Excel form  →  LrsEventForm.field_info()  →  create local GDB feature class
                                          →  add custom fields
                                          →  CopyFeatures to SDEADM.TRNLRS in SDE
                                          →  EnableEditorTracking (ADDBY/ADDDATE/MODBY/MODDATE UTC)
                                          →  AddGlobalIDs
                                          →  CreateLRSEventFromExistingDataset
                                          →  ModifyEventBehaviorRules
                                          →  RegisterAsVersioned (branch)
```

**Excel form sheets:**
- `DATASET DETAILS` (or custom `sheet_name`) — field schema (FieldName, Field Type, Field Length, Alias, Domain)
- `Event Behaviors` — behaviour rules (header on row 2)

**Standard fields** are skipped when adding fields — `LrsEventForm.standard_fields`:
```python
("OBJECTID", "FROMDATE", "TODATE", "EVENTID", "ROUTEID", "LOCERROR", "SHAPE")
```

To run:
```python
xls_info = {
    r"T:\...\MyEvent_New_Event_Request.xlsx": {
        'sheet_name': 'DATASET DETAILS',
        'event_name': "E_MyEvent"
    },
}
```

---

## Event Behaviour Rules

Controls what happens to an event when the underlying route changes.
Set via `arcpy.locref.ModifyEventBehaviorRules`.

| Activity | Valid values |
|---|---|
| `CALIBRATE` | `STAY_PUT`, `RETIRE`, `MOVE` |
| `RETIRE` | `STAY_PUT`, `RETIRE`, `MOVE` |
| `EXTEND` | `STAY_PUT`, `RETIRE`, `MOVE`, `COVER` |
| `REASSIGN` | `STAY_PUT`, `RETIRE`, `MOVE`, `SNAP` |
| `REALIGN` | `STAY_PUT`, `RETIRE`, `MOVE`, `SNAP`, `COVER` |
| `REVERSE` | `STAY_PUT`, `RETIRE`, `MOVE` |
| `CARTO_REALIGN` | `HONOR_ROUTE_MEASURE`, `HONOR_REFERENT_LOCATION` |

Use `"#"` to leave an activity unchanged.

---

## LOCERROR Handling (`measure_updates.py`)

After route edits, some events end up with location errors. The `update_service_tomeasures`
function fixes them via the Portal REST API / ArcGIS Python API.

Handled error types:
- `"PARTIAL MATCH FOR THE TO-MEASURE"` — `TOMEASURE` is slightly beyond the route end.
  Fix: compare event `TOMEASURE` against `LRSN_Route.SHAPE.STLength()`;
  if within `measure_threshold` (30 m), snap to route length.
- `"ROUTE LOCATION NOT FOUND"` — export, fix `MEASURE`, delete from service,
  re-append with `arcpy.locref.AppendEvents`, then `GenerateEvents`.

Portal connection config keys: `[Portal_Admin]` → `username`, `password`, `url`.
LRS service URL pattern: `{portal_url}/extn/rest/services/LRS_EventEditor/FeatureServer/{layer_index}`
(currently layers 0–42).

---

## Generating Intersections

```python
arcpy.locref.GenerateIntersections(
    in_intersection_feature_class="SDEADM.TRNLRS\SDEADM.INT_RouteOnRoute",
    in_network_layer="SDEADM.TRNLRS\SDEADM.LRSN_Route",
    start_date=None,
    edited_by_current_user="ALL_USERS"
)
```

Requires branch-versioned connection and Location Referencing Extension.

---

## Shared File Locations

| Path | Contents |
|---|---|
| `\\msfs203.hrm.halifax.ca\GISData\Data Sharing\LRS_operational\lrs_view.gdb` | Operational LRS GDB (`lrs_view.gdb`) |
| `T:\work\giss\monthly\YYYYMM*\gallaga\<EventName>\` | New event request Excel forms |
| `E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde` | Prod branch RW connection |
| `E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde` | QA branch RW connection |
| `E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm_branch.sde` | Dev branch RW connection |

---

## License Pattern

```python
if arcpy.CheckExtension("LocationReferencing") == "Available":
    arcpy.CheckOutExtension("LocationReferencing")
else:
    raise LicenseError("Unable to checkout Location Referencing License.")

try:
    ...
finally:
    arcpy.CheckInExtension("LocationReferencing")
```

Always check in the extension in a `finally` block.
