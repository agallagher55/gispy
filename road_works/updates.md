# RoadWorks — Adding a User to a Dropdown

This document describes the end-to-end workflow for adding a person's name to a
dropdown field in the RoadWorks Map Editor application.

---

## Background

Dropdown fields in the application (e.g. **Reviewed By**, **Approved By**) are
backed by coded-value domains in the SDE geodatabase. Adding a user means adding
a new code/description pair to the relevant domain(s). The domain sorts
alphabetically on save.

---

## Step 1 — Identify the correct domain(s)

Determine which layer(s) the user needs access to, then map to the domain:

| Access needed               | Field on feature class      | Domain to update              |
|-----------------------------|-----------------------------|-------------------------------|
| Encroachment editor         | `REVIEWED_BY`               | `TRN_RDM_EncroachEditors`     |
| Road closure editor         | `REVIEWED_BY`               | `TRN_RDM_RoadClosureEditors`  |
| Road closure approver       | `APPROVED_BY`               | `TRN_RDM_RoadClosureApprover` |

A user needing access to multiple layers requires an entry in each relevant domain.

---

## Step 2 — Update `ADD_CODE_VALUES` in the script

Open `scripts/update_domain_codes.py` and add the person's full name to each
applicable domain. Code and description must be identical.

```python
ADD_CODE_VALUES = {
    "TRN_RDM_RoadClosureEditors": {
        "Jane Smith": "Jane Smith",
    },
    # Add to a second domain if the user also needs encroachment access:
    # "TRN_RDM_EncroachEditors": {
    #     "Jane Smith": "Jane Smith",
    # },
}
```

Leave `REMOVE_CODE_VALUES` empty (or commented out) unless you are also removing
someone in the same run.

---

## Step 3 — Run dev and verify

In the `for dbs in [...]` block, uncomment **only** the dev block:

```python
for dbs in [
    [
        config.get("SERVER", "dev_rw"),
        config.get("SERVER", "dev_ro"),
        config.get("SERVER", "dev_web_ro_gdb"),
    ],
    # qa and prod remain commented out
]:
```

Run the script from the app server (or locally with `[LOCAL]` config keys).
Check the log — confirm the domain code was added and the sort completed without
errors before continuing.

---

## Step 4 — Promote to QA

Comment out the dev block and uncomment QA:

```python
for dbs in [
    [
        config.get("SERVER", "qa_rw"),
        config.get("SERVER", "qa_ro"),
        config.get("SERVER", "qa_web_ro_gdb"),
    ],
]:
```

Run and verify the log.

---

## Step 5 — Promote to Production

Comment out QA and uncomment prod:

```python
for dbs in [
    [
        config.get("SERVER", "prod_rw"),
        config.get("SERVER", "prod_ro"),
        config.get("SERVER", "prod_web_ro_gdb"),
    ],
]:
```

Run and verify the log.

---

## Step 6 — Restart the ArcGIS Server service

ArcGIS Server caches the map service definition (including domain values) at
start-up, so the domain change is not visible in the application until the
relevant service is restarted. Do this after each environment's script run.

Restart the appropriate service in the **Editing** folder on ArcGIS Server
Manager for the environment you just updated:

| Layer updated               | Service to restart  |
|-----------------------------|---------------------|
| Encroachments               | `Encroachment`      |
| Street Closures             | `StreetClosure`     |
| Sidewalk Repair Closures    | `SidewalkRepair`    |

After the service comes back online, the new name will appear in the dropdown.

---

## Notes

- Always run one environment at a time. Never uncomment multiple environments in
  a single run.
- All three connections for each environment (rw, ro, web_ro_gdb) are processed
  together to keep domains in sync.
- The script automatically sorts the domain alphabetically by description after
  each add, so the new name will appear in the correct position in the dropdown.
- When testing locally (not on the app server), the script uses `[LOCAL]` config
  keys and creates a `scratch.gdb` to validate domain operations before touching
  SDE.
