# Parcel Load Script Documentation

This document explains the current parcel load workflow for `parcelload/scripts/main.py`, including the manual file-download step from the province file transfer site, and identifies opportunities to improve/automate the process.

## Script scope

Primary script:
- `parcelload/scripts/main.py`

Support scripts/files:
- `parcelload/scripts/prepare_workspace.py`
- `parcelload/scripts/sql_cmds.py`
- `parcelload/config.ini`
- `parcelload/sqls/*.sql`

---

## Current end-to-end process (as done today)

### 0) Get the source data (manual)

1. Open the provincial file transfer site: `https://sfts1.gov.ns.ca/`.
2. Download the latest parcel/LINNS extract ZIP package.
3. Retrieve the ZIP password from the email that accompanies the transfer.
4. Unzip the package into the configured parcel-load folder (see `PARCEL_LOAD_DIR` in `parcelload/config.ini`).
5. Confirm expected files exist in the extract folder (for example: `pidaantax.dbf`, `pidnames.dbf`, `pidrelate.dbf`, `pidaddress.dbf`, `piddocs.dbf`, `pidplans.dbf`, `pidretire.dbf`, `pidmstrs.dbf`, and required shapefiles).

### 1) Configure paths

1. Open `parcelload/config.ini`.
2. Validate all path settings referenced by `main.py`, especially:
   - SDE connection files (`SDE_RW`, `SDE_RO`)
   - parcel feature targets in RW/RO
   - `PARCEL_LOAD_DIR`
   - `PIDMSTRS_DBF`

### 2) Prepare the workspace

Run:

```bash
python prepare_workspace.py
```

This prepares intermediate/workspace data used later by `main.py`.

### 3) Run the main parcel load script

Run:

```bash
python main.py
```

`main.py` performs the following high-level actions:

1. **Run preflight checks** to validate required DBFs/shapefiles, SQL files, and ArcGIS datasets/connections.
2. **Back up existing parcel point data** and truncate old-point target table.
3. **Truncate and load LINNS tables** using the downloaded DBF files.
4. **Load LINNS PIDMSTRS** (special handling from `pidmstrs.dbf`).
5. **Truncate and load RW spatial parcel layers** (`point/line/polygon/ghosted line`).
6. **Regenerate parcel point outputs** from polygon geometry.
7. **Run SQL post-processing** scripts for PID reporting and fcode/batch updates.
8. **Write `qa_summary.csv`** with final row counts and key checks.

### 4) Manual validation and downstream actions

After script completion:

1. Review script logs (`script_logs.log`) for errors/warnings.
2. Review generated new PID report output.
3. Review `qa_summary.csv` for final counts/check statuses.
4. Confirm expected record counts and spot-check key layers/tables.
5. Run any required RO sync/append procedures if not already automated in your operational runbook.

---

## Practical run checklist

Use this quick checklist each run:

- [ ] Download latest ZIP from `https://sfts1.gov.ns.ca/`
- [ ] Get password from email and extract files
- [ ] Confirm DBF/shapefile inputs are present in parcel-load folder
- [ ] Verify `parcelload/config.ini` paths
- [ ] Run `python prepare_workspace.py`
- [ ] Run `python main.py`
- [ ] Review logs and outputs
- [ ] Review `qa_summary.csv`
- [ ] Perform post-run QA checks

---

## Areas for improvement, optimization, or simplification

### A) Automate the file intake from SFTS (highest value)

Current pain point: manually browsing, downloading, reading email password, and unzipping.

Potential improvements:

1. **Automated downloader script**
   - If SFTS supports API/SFTP/WebDAV/automatable auth, create a scheduled Python job to fetch the newest file.
   - Save with date-stamped filename and checksum.

2. **Automated secure unzip**
   - Store password in a secure secret store (Windows Credential Manager, environment secret, enterprise vault).
   - Use a non-interactive extraction step (for example `7z` CLI or Python library supporting encrypted ZIPs).

3. **Inbox-assisted password capture (semi-automated)**
   - If policy allows, parse designated mailbox for the latest password email.
   - Match password email to download timestamp/package.

4. **Atomic staging folder**
   - Download to `incoming/`, validate contents, then move to `ready/` once complete.
   - Prevents partial/incomplete file usage.

### B) Make `main.py` workflow modular and explicit

1. Add CLI flags (`--step backup`, `--step linns`, `--step rw-load`, `--step sql`, `--all`).
2. Split current monolithic run into resumable stages with checkpoints.
3. Save run-state manifest (`run_YYYYMMDD.json`) to support restart after failure.

### C) Improve robustness and observability

1. Add preflight validation:
   - missing file checks
   - schema/field checks
   - SDE connectivity checks
2. Fail fast with clear actionable errors.
3. Add row-count reconciliation report (before/after counts for each target).
4. Standardize structured logs and summarize success/failure at end.

### D) Reduce manual database operations

1. Where safe, convert manual truncation/append operations into scripted functions.
2. Centralize field mappings used in append calls into config/constants.
3. Wrap SQL execution in transaction-aware helper with clearer success criteria.

### E) Simplify configuration management

1. Use environment profiles (`dev/qa/prod`) to avoid editing one config file repeatedly.
2. Validate config keys at startup and print a concise run plan.
3. Keep sensitive values out of plaintext config where possible.

---

## Suggested next implementation steps

1. Build `download_extract.py` for SFTS intake (download + password unzip + validation).
2. Update `main.py` to accept input folder and run-mode arguments.
3. Add a `preflight_check()` that blocks execution when required files are missing.
4. Add a final `qa_summary.csv` with counts/checks.
5. Schedule full pipeline via Task Scheduler (or enterprise scheduler) once stable.

---

## Notes

- Keep `steps.txt` synchronized with this document so quick-start and full documentation do not diverge.
- If SFTS automation is restricted by policy, a semi-automated approach (single command after manual download) still removes most of the repetitive effort.
