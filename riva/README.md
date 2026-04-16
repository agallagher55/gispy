# RIVA Street ETL (`riva/main.py`)

An ArcPy ETL script that synchronises the `TRN_STREET_RIVA` table with HRM's authoritative street data. The process runs in three sequential steps, pausing at the end for a manual truncate-and-load back to the live SDE environment.

---

## What it does

### Step 1 — Append new HRM streets

1. Creates (or reuses) a local `scratch.gdb` file geodatabase in the scripts directory.
2. Backs up the current `TRN_STREET_RIVA` table into `scratch.gdb`.
3. Selects all HRM-owned streets from `TRN_street` (`OWN LIKE 'HRM'`).
4. Removes any street whose `FDMID` already exists in the non-retired records of `TRN_STREET_RIVA`.
5. Exports the remaining (net-new) streets to `TBL_new_streets_for_riva`.
6. Appends those records into the local `TRN_STREET_RIVA` copy.

### Step 2 — Mark retired streets

1. Identifies streets that are present in `TRN_STREET_RIVA` (with `DATE_RET IS NOT NULL`) but are no longer in `TRN_street` — these are newly retired.
2. Pulls matching records from `TRN_street_retired`.
3. Updates the following fields in the local `TRN_STREET_RIVA` copy:

   | Field          | Source                          |
   |----------------|---------------------------------|
   | `DATE_RET`     | `TRN_street_retired.DATE_RET`   |
   | `DATE_REV`     | Today's date                    |
   | `OLD_FDMID`    | `TRN_street_retired.OLD_FDMID`  |
   | `SHAPE_LENGTH` | `TRN_street_retired.SHAPE@LENGTH` |
   | `DATE_ACT`     | `TRN_street_retired.DATE_ACT`   |

### Step 3 — Sync existing (active) streets

1. For every non-retired record in `TRN_STREET_RIVA`, checks whether the geometry length differs from `TRN_street`.
2. If the length has changed (the common case), updates:

   | Field          | Calculation / Source                                                  |
   |----------------|-----------------------------------------------------------------------|
   | `SHAPE_LENGTH` | `TRN_street.SHAPE@LENGTH`                                             |
   | `SHORT_DESC`   | `FULL_NAME (FROM_STR TO TO_STR)`                                      |
   | `LONG_DESC`    | `FULL_NAME GSA_LEFT`                                                  |
   | `OLD_FDMID`    | `TRN_street.OLD_FDMID`                                                |
   | `DATE_REV`     | Today's date                                                          |
   | `DATE_ACT`     | `TRN_street.DATE_ACT`                                                 |
   | `SYS_DATE`     | `TRN_street.SYS_DATE`                                                 |

### Manual finalisation

After all three steps complete, the script pauses twice and prompts the operator to:

1. Truncate and reload the live read-write SDE table.
2. Truncate and reload `ASSET_ACCOUNTING.TRN_STREET_RIVA`.

---

## Inputs

| Source                                      | Description                                           |
|---------------------------------------------|-------------------------------------------------------|
| `SDEADM.TRN_streets_routes\SDEADM.TRN_street` | Authoritative HRM street network (feature class)    |
| `SDEADM.TRN_STREET_RIVA`                   | Existing RIVA street table (SDE)                      |
| `SDEADM.TRN_street_retired`                 | Retired/historical street records (SDE)               |
| SDE connection file                         | Hardcoded to `E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde` — update as needed |

---

## Outputs

| Output                                  | Location                        | Description                                            |
|-----------------------------------------|---------------------------------|--------------------------------------------------------|
| `scratch.gdb`                           | `<scripts_dir>/scratch.gdb`     | Local file GDB created (or reused) each run            |
| `TRN_STREET_RIVA` (backup)              | `scratch.gdb`                   | Pre-run backup of the RIVA table                       |
| `TRN_street_HRMowned`                   | `scratch.gdb`                   | Intermediate — HRM-owned streets filtered from source  |
| `trn_street_new_streets_riva`           | `scratch.gdb`                   | Intermediate — net-new streets not yet in RIVA         |
| `TBL_new_streets_for_riva`              | `scratch.gdb`                   | Intermediate table exported before append              |
| `TRN_street_new_retired_streets_riva`   | `scratch.gdb`                   | Intermediate — newly retired streets (Step 2 only)     |
| Updated `TRN_STREET_RIVA` (local copy)  | `scratch.gdb`                   | Final reconciled RIVA table, ready for truncate-and-load |

---

## Dependencies

- **ArcPy** (ArcGIS Pro or ArcGIS Desktop)
- `utils.py` — provides `create_fgdb()` and other shared helpers
- A valid SDE connection file pointing to an environment with read-write access to the three source feature classes/tables

---

## Known limitations / TODOs

- The SDE connection path is hardcoded; consider moving it to `config.ini`.
- Step 2 retirement detection logic is inverted in comments vs. implementation — review the `DATE_RET IS NOT NULL` filter.
- The final truncate-and-load steps are manual; the script does not write changes back to SDE automatically.
- QA check noted in code: `SHORT_DESC`, `LONG_DESC`, `DATE_REV`, and `FDMID 700013207` should not be blank after a run.
