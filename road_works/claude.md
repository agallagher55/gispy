# RoadWorks — Claude Code Reference

## Overview

The **RoadWorks Map - Editor App** is an ArcGIS Web AppBuilder application that allows
permissioned HRM staff to draw and attribute road-related closures on a map. The features
they create are stored in the enterprise geodatabase (SDE) and served through dedicated
ArcGIS Server map services in the **Editing** folder.

My role: when a user needs editing access to the application, I add them to the
appropriate editor/approver domain(s) in the geodatabase so their name appears as a
selectable value in the relevant attribute field.

---

## Application layers and backing services

| App layer                     | ArcGIS Server service | Known SDE feature class          |
|-------------------------------|-----------------------|----------------------------------|
| Street Closures               | `StreetClosure`       | TBD                              |
| Sidewalk Closures/Disruptions | TBD                   | TBD                              |
| Sidewalk Repair Closures      | `SidewalkRepair`      | TBD                              |
| Encroachments                 | `Encroachment`        | `SDEADM.TRN_ENCROACHMENT`        |

All services live in the **Editing** folder on the ArcGIS Server.

---

## Permission domains

Access is controlled by coded-value domains whose names end in **`Editors`** or
**`Approver`**. These domains are assigned to specific fields on the feature classes.

| Domain                       | Controls                                   |
|------------------------------|--------------------------------------------|
| `TRN_RDM_EncroachEditors`    | Who can be recorded as an encroachment editor   |
| `TRN_RDM_RoadClosureEditors` | Who can be recorded as a road closure editor    |
| `TRN_RDM_RoadClosureApprover`| Who can approve road closures                   |

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
    "TRN_RDM_RoadClosureEditors": {
        "Jane Smith": "Jane Smith",
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
