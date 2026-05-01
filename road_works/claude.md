# RoadWorks — Claude Code Reference

## Overview

The [**RoadWorks Map - Editor App**](https://hrm.maps.arcgis.com/apps/webappviewer/index.html?id=c00fdee3e1614cc3ac3e19a1dde6e5a9), is an ArcGIS Web AppBuilder application that allows
permissioned HRM staff to draw and attribute road-related closures on a map. The features
they create are stored in the enterprise geodatabase (SDE) and served through dedicated
ArcGIS Server map services in the **Editing** folder.

My role: when a user needs editing access to the application, I add them to the
appropriate editor/approver domain(s) in the geodatabase so their name appears as a
selectable value in the relevant attribute field.

---

## Application layers and backing services

| App layer                     | ArcGIS Server service | Known SDE feature class            |
|-------------------------------|-----------------------|------------------------------------|
| Street Closures               | `StreetClosure`       | `SDEADM.TRN_street_closure`        |
| Sidewalk Closures/Disruptions | `SidewalkRepair`      | `SDEADM.TRN_encroachment`          |
| Sidewalk Repair Closures      | `SidewalkRepair`      | `SDEADM.TRN_encroachment`          |
| Encroachments                 | `Encroachment`        | `SDEADM.TRN_encroachment`          |

All services live in the **Editing** folder on the ArcGIS Server:
`https://gis-web-int.halifax.ca/extn/manager/#f=Editing`

---

## Feature class field schemas

### `SDEADM.TRN_encroachment`

| Field Name   | Alias            | Type      | Allow NULL | Domain                   | Length |
|--------------|------------------|-----------|------------|--------------------------|--------|
| OBJECTID     | OBJECTID         | Object ID |            |                          |        |
| TYPE         | Type             | Text      |            | TRN_RDM_EncroachTypes    | 50     |
| PERMIT_NO    | Permit Number    | Text      |            |                          | 50     |
| REVIEWED_BY  | Reviewed By      | Text      |            | TRN_RDM_EncroachEditors  | 50     |
| START_DATE   | Start Date       | Date      | ✓          |                          |        |
| END_DATE     | End Date         | Date      | ✓          |                          |        |
| COMMENTS     | Public Comments  | Text      | ✓          |                          | 255    |
| ATTACHMENTS  | Attachments      | Text      | ✓          |                          | 255    |
| ADDBY        | Add By           | Text      | ✓          |                          | 32     |
| ADDDATE      | CreationDate     | Date      | ✓          |                          |        |
| MODBY        | Modified By      | Text      | ✓          |                          | 32     |
| MODDATE      | EditDate         | Date      | ✓          |                          |        |
| GLOBALID     | GLOBALID         | Global ID |            |                          |        |
| REMARKS      | Internal Remarks | Text      | ✓          |                          | 255    |
| STREET_NAME  | Street Name      | Text      |            | TRN_StreetName           | 50     |
| FROM_STR     | From Street      | Text      |            | TRN_StreetName           | 50     |
| TO_STR       | To Street        | Text      |            | TRN_StreetName           | 50     |
| RDMID        | RDMID            | Long      | ✓          |                          |        |
| SHAPE        | SHAPE            | Geometry  | ✓          |                          |        |

### `SDEADM.TRN_street_closure`

| Field Name       | Alias             | Type      | Allow NULL | Domain                      | Default     | Length |
|------------------|-------------------|-----------|------------|-----------------------------|-------------|--------|
| OBJECTID         | OBJECTID          | Object ID |            |                             |             |        |
| CLOSURE_TYPE     | Closure Type      | Text      |            | TRN_RDM_RoadClosureType     |             | 50     |
| CLOSURE_STAGE    | Closure Stage     | Text      |            | TRN_RDM_RoadClosureStage    | In Progress | 50     |
| START_DATE       | Start Date        | Date      | ✓          |                             |             |        |
| END_DATE         | EndDate           | Date      | ✓          |                             |             |        |
| START_TIME       | StartTime         | Text      | ✓          |                             |             | 50     |
| END_TIME         | EndTime           | Text      | ✓          |                             |             | 50     |
| ALT_START_DATE   | Alt Start Date    | Date      | ✓          |                             |             |        |
| ALT_END_DATE     | Alt End Date      | Date      | ✓          |                             |             |        |
| REOPEN_EVENINGS  | Re-Open Evening   | Text      | ✓          | TRN_RDM_YesNo               |             | 50     |
| REOPEN_WEEKENDS  | Re-Open Weekends  | Text      | ✓          | TRN_RDM_YesNo               |             | 50     |
| PERMIT_NO        | Permit Number     | Text      | ✓          |                             |             | 100    |
| APPLICATION_DATE | Application Date  | Date      | ✓          |                             |             |        |
| REVIEWED_BY      | Reviewed By       | Text      | ✓          | TRN_RDM_RoadClosureEditors  |             | 50     |
| REVIEW_DATE      | Review Date       | Date      | ✓          |                             |             |        |
| APPROVED_BY      | Approved By       | Text      | ✓          | TRN_RDM_RoadClosureApprover |             | 50     |
| APPROVED_DATE    | Approved Date     | Date      | ✓          |                             |             |        |
| REQUEST_BY       | Request By        | Text      | ✓          |                             |             | 100    |
| CHARGE_TO        | Charge To         | Text      | ✓          |                             |             | 100    |
| DETOUR_URL       | Detour Link       | Text      | ✓          |                             |             | 255    |
| COMMENTS         | Public Comments   | Text      | ✓          |                             |             | 255    |
| ATTACHMENTS      | Attachments       | Text      | ✓          |                             |             | 255    |
| ADDBY            | Add By            | Text      | ✓          |                             |             | 32     |
| ADDDATE          | Add Date          | Date      | ✓          |                             |             |        |
| MODBY            | Modified By       | Text      | ✓          |                             |             | 32     |
| MODDATE          | Modified Date     | Date      | ✓          |                             |             |        |
| GLOBALID         | GLOBALID          | Global ID |            |                             |             |        |

---

## Permission domains

Access is controlled by coded-value domains whose names end in **`Editors`** or
**`Approver`**. These domains are assigned to specific fields on the feature classes.

| Domain                       | Controls                                                 |
|------------------------------|----------------------------------------------------------|
| `TRN_RDM_EncroachEditors`    | Who can be recorded as an encroachment editor            |
| `TRN_RDM_RoadClosureEditors` | Who can be recorded as a road/sidewalk closure editor    |
| `TRN_RDM_RoadClosureApprover`| Who can approve road closures                            |

**Domain code convention:** code and description are always identical and use the
person's full name.

```python
"Full Name": "Full Name"   # e.g. "Jane Smith": "Jane Smith"
```

---

## Script: `scripts/update_domain_codes.py`

This is the standard script for adding or removing users from RoadWorks domains.

### Key dictionaries

```python
ADD_CODE_VALUES = {
    "TRN_RDM_RoadClosureEditors": {},
    "TRN_RDM_RoadClosureApprover": {},
    "TRN_RDM_EncroachEditors": {
        'Kayode Taiwo': "Kayode Taiwo",
    },
}

REMOVE_CODE_VALUES = {
    # "TRN_RDM_RoadClosureEditors": ["Jane Smith"],
}
```

- Add a user → put them in `ADD_CODE_VALUES` under the relevant domain(s).
- Remove a user → put their **code** (full name string) in `REMOVE_CODE_VALUES`.
- A person needing access to multiple layers goes into multiple domain entries.

### Promotion workflow

Run one environment at a time. Review the log after each before promoting.

```python
# Step 1 — dev only (uncomment dev block, comment qa and prod)
[config.get("SERVER", "dev_rw"),
 config.get("SERVER", "dev_ro"),
 config.get("SERVER", "dev_web_ro_gdb")]

# Step 2 — qa (if dev succeeded)
[config.get("SERVER", "qa_rw"),
 config.get("SERVER", "qa_ro"),
 config.get("SERVER", "qa_web_ro_gdb")]

# Step 3 — prod (if qa succeeded)
[config.get("SERVER", "prod_rw"),
 config.get("SERVER", "prod_ro"),
 config.get("SERVER", "prod_web_ro_gdb")]
```

All three connections for a given environment (rw, ro, web_ro_gdb) are always updated
together so domains stay in sync across read-write, read-only, and web GDB connections.

### Config

`scripts/config.ini` — SERVER section only (script always runs from the app server).

```ini
[SERVER]
dev_rw  = E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde
dev_ro  = E:\HRM\Scripts\SDE\SQL\Dev\dev_RO_sdeadm.sde
dev_web_ro_gdb = \\msfs06\GISApp\AGS_Dev\fgdbs\web_RO.gdb

qa_rw  = E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde
qa_ro  = E:\HRM\Scripts\SDE\SQL\qa_RO_sdeadm.sde
qa_web_ro_gdb  = \\msfs06\GISApp\AGS_QA\fgdbs\web_RO.gdb

prod_rw = E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde
prod_ro = E:\HRM\Scripts\SDE\SQL\Prod\prod_RO_sdeadm.sde
prod_web_ro_gdb = \\msfs06\GISApp\AGS_Prod\fgdbs\web_RO.gdb
```

---

## Typical task shape

> "Add Jane Smith as a road closure editor."

1. Add `"Jane Smith": "Jane Smith"` to `TRN_RDM_RoadClosureEditors` in `ADD_CODE_VALUES`.
2. Run dev → confirm log → run qa → confirm log → run prod.

> "Remove John Doe from encroachment editors."

1. Add `"John Doe"` to `REMOVE_CODE_VALUES["TRN_RDM_EncroachEditors"]`.
2. Same dev → qa → prod promotion.

---

## Key modules (from parent package)

| Module        | Relevant function(s)                                      |
|---------------|-----------------------------------------------------------|
| `domains.py`  | `add_code_value()`, `remove_code_value()`, `domains_in_db()`, `transfer_domains()` |
| `utils.py`    | `create_fgdb()` (used to create scratch.gdb for local testing) |
