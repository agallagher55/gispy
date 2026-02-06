# Parcel Load - Code Review

## Overview

The `parcelload` system is a monthly GIS ETL pipeline for Halifax Regional Municipality (HRM) that ingests provincial parcel boundary data (shapefiles + LINNS DBF tables), loads it into ArcSDE geodatabases (read-write and read-only), and classifies government-owned parcels. The workflow spans ~2,500 lines of Python across two sub-modules (`scripts/` and `Prov_Fed_Parcels/`), four SQL scripts, and a shared `config.ini`.

---

## Bugs and Functional Issues

### 1. `enable_sde_edits` decorator calls `startOperation()` twice (Prov_Fed_Parcels/main.py:43-60)

```python
edit.startEditing(True, True)
edit.startOperation()
result = function(*args, **kwargs)
edit.startOperation()   # <-- should be edit.stopOperation()
edit.stopEditing(True)
```

The second `edit.startOperation()` should be `edit.stopOperation()`. This will either throw an error at runtime or silently leave the edit session in an inconsistent state, potentially causing data corruption in the `LND_PARCEL_GOVOWN_LOOKUP` table.

### 2. Misleading error messages in `truncate_load_linns_all_rw()` and `load_linns_all()` (scripts/main.py:519-520, 597-598)

```python
if row_count > 0:
    arcpy.TruncateTable_management(...)
else:
    raise ValueError("Did not find any records in the backup. Check backup was made successfully...")
```

These functions are truncating *target* tables before loading, not working with backups. If the table happens to be empty (e.g., first load or prior truncation), the error message is misleading and will block legitimate execution. The guard should check that the *source* has rows, not the target.

### 3. Broken area-value validation in `load_linns_pidmstrs()` (scripts/main.py:454)

```python
if all([x == 0.0 for x in sde_linns_area]) > 0:
    raise ValueError(...)
```

`all()` returns a boolean (`True`/`False`). Comparing `True > 0` evaluates to `True` (since `True == 1`), so this accidentally works - but only when **every** area is `0.0`. The `> 0` comparison is misleading and suggests the author intended a count-based check. Additionally, `num_area_null` (line 453) is computed but never used.

### 4. Area-value comparison uses wrong type in `load_pidmstrs_ro()` (scripts/main.py:574)

```python
if all([x == "" for x in area_values]):
```

Area values from the database are likely numeric (float/int), not empty strings. This check would never trigger for numeric fields, making the validation ineffective.

### 5. `update_parcel_pt()` only loads multi-point, skips single-point (scripts/main.py:280-288)

The function truncates both `lnd_parcel_point_multi_sde_rw` and `lnd_parcel_point_single_sde_rw`, but only appends data to the multi-point feature. The single-point feature is left truncated and empty. This appears to be an incomplete implementation.

### 6. Undefined variable `NAD83_SHP_Parcel_Line` in `prepare_prov_shapefiles()` (scripts/prepare_workspace.py:319-320)

```python
arcpy.Select_analysis(NAD83_SHP_Parcel_Line, select_parcel_line, "THEME_NO = 1001")
arcpy.Select_analysis(NAD83_SHP_Parcel_Line, select_ghosted_line, "THEME_NO = 4700")
```

`NAD83_SHP_Parcel_Line` and `NAD83_SHP_Parcel_Polygon` are defined in the `__main__` block (line 394-395) but referenced inside `prepare_prov_shapefiles()`, which runs in a different scope. This function will crash with a `NameError` unless called from `__main__` with these globals already set. The projected feature paths should be passed in via the `feature_info` dict or as explicit parameters.

### 7. Unused `workspace` parameter in `query_prov_shapefiles()` (scripts/prepare_workspace.py:207-210)

```python
def query_prov_shapefiles(workspace=PARCEL_LOAD_DIR):
    workspace_files = os.listdir(PARCEL_LOAD_DIR)  # uses module-level constant, not parameter
```

The function accepts `workspace` but uses the module-level `PARCEL_LOAD_DIR` constant instead for listing files. It does use `workspace` for `os.path.join()` calls later, so this is a partial bug - the file listing and the path joining could disagree if a different workspace is passed.

### 8. `db.py` has broken indentation (Prov_Fed_Parcels/db.py)

The `sql_script()` function mixes 2-space and 4-space indentation, resulting in an `IndentationError` if ever imported. This file is currently unused but would fail on import.

### 9. Missing `metadata` module (scripts/main.py:13-16)

```python
from metadata import (
    get_sde_metadata,
    update_metadata,
)
```

No `metadata.py` file exists in the repository. The script will fail on import unless this module exists elsewhere on `sys.path` in the production environment.

---

## Structural and Design Issues

### 10. Duplicated code between `scripts/main.py` and `scripts/lnd_parcel_point.py`

`parcel_poly_to_point()` and `update_parcel_pt()` are duplicated almost verbatim across both files. The standalone `lnd_parcel_point.py` version references an undefined `local_gdb` variable (line 74), making it non-functional. One copy should be the single source of truth.

### 11. Duplicated logging setup across all scripts

Each of `scripts/main.py`, `scripts/prepare_workspace.py`, `scripts/lnd_parcel_point.py`, `scripts/remove_field_default.py`, and `Prov_Fed_Parcels/logger.py` independently configures logging with the same format string. This should be a shared utility.

### 12. Hard-coded paths scattered throughout

- `scripts/main.py:291` - Default workspace: `r"C:\Workspace\Parcel_Load\Scratch"`
- `scripts/main.py:707-708` - PID report output: `r"T:\work\giss\tools\Parcel Load\..."`
- `scripts/sql_cmds.py:35,37` - Hard-coded T-drive paths for output files
- `Prov_Fed_Parcels/main.py:30-32` - Hard-coded SDE paths per user (`gallaga`)
- `Prov_Fed_Parcels/utils.py:7` - Hard-coded SDE path per user

These should all come from `config.ini` or environment variables.

### 13. Mixed use of `logger` vs `logging` vs `print` vs `arcpy.AddMessage`

The codebase inconsistently uses four different output mechanisms:
- `logger.info()` (module-level logger)
- `logging.info()` (root logger - goes to a different destination)
- `print()` (stdout only)
- `arcpy.AddMessage()` (ArcGIS tool output only)

For example, `scripts/main.py:222` uses `logging.info()` (root logger) while the rest of the function uses `logger.info()` (module logger). This means some messages will silently go to different destinations or be lost entirely.

### 14. No transaction safety for multi-table operations

The main workflow truncates and loads multiple tables sequentially. If it fails mid-way (e.g., during step 5 of 8), the database is left in a partially updated state with no rollback capability. The SQL scripts do use `BEGIN TRANSACTION`/`COMMIT`, but the Python-side arcpy operations do not.

### 15. `Prov_Fed_Parcels` module is disconnected from `config.ini`

The `Prov_Fed_Parcels/main.py` module hard-codes its own SDE paths (lines 30-34) rather than reading from the shared `config.ini`. There's even a TODO on line 40: `# TODO: Add config file`.

---

## Security and Operational Concerns

### 16. `os.startfile()` call in production script (scripts/main.py:709)

```python
os.startfile(r"T:\work\giss\tools\Parcel Load\Parcel Load sqls")
```

This opens a file explorer window during an automated pipeline, which is fragile and inappropriate for headless/scheduled execution.

### 17. `input()` calls block automated execution (scripts/main.py:794-808)

Four `input()` calls at the end of `main.py` require manual keyboard interaction, preventing the script from running unattended via Task Scheduler.

### 18. SQL files contain hard-coded server names

All SQL scripts reference `[GISRW01]` directly. If the server name changes or the scripts need to run against a different environment (dev/QA), every SQL file must be manually edited.

### 19. Email addresses in source code (scripts/main.py:714-723)

Internal email addresses are committed to source control. These should be in configuration.

### 20. Raw SQL passed to `ArcSDESQLExecute` without parameterization (scripts/sql_cmds.py)

The `execute_sql()` function reads a SQL file and executes it directly. While the current SQL files don't have user input, the pattern doesn't guard against future misuse. The `pid_report()` function also constructs a SQL `IN` clause via string concatenation (line 42).

---

## Code Quality Issues

### 21. Shadowed built-in: `type` variable (Prov_Fed_Parcels/main.py:288)

```python
type = filtered_new_pid_info[pid].get("TYPE", "")
```

This shadows Python's built-in `type()` function within the loop scope.

### 22. Incorrect f-string in logging (scripts/main.py:689)

```python
logger.info(f"{datetime.now()}Running SQL scripts...")
```

Missing space between the timestamp and the message text.

### 23. Redundant `del cursor` after `with` statement is unnecessary

`scripts/main.py:441` has `del cursor` after a `with` block, but some cursor usages don't use `with` at all (e.g., `Prov_Fed_Parcels/main.py:285-304`), risking unclosed cursors if an exception occurs.

### 24. Bare `except` in `db.py` (Prov_Fed_Parcels/db.py:33)

```python
except:
    print("Error executing SQL*Plus script.")
    raise
```

Catches all exceptions including `KeyboardInterrupt` and `SystemExit`.

### 25. `PYTHON_9.3` expression type in field calculations (scripts/prepare_workspace.py:357-369)

```python
arcpy.CalculateField_management(feature, "SOURCE", "\"LIC-PROPMAP\"", "PYTHON_9.3", "")
```

`PYTHON_9.3` is the legacy ArcMap expression type. ArcGIS Pro uses `PYTHON3`. While Pro may still accept `PYTHON_9.3` for backward compatibility, this should be updated.

### 26. Unused import: `re` in `prepare_workspace.py`

The `re` module is imported (line 10) and used, but the regex logic in `query_prov_shapefiles()` (lines 237-244) has an issue: if the pattern doesn't match, `year` and `month` are undefined, and the code proceeds to use them on line 255, which would raise `NameError`.

### 27. Date format comment is wrong (scripts/main.py:68)

```python
CURRENT_MONTH = datetime.now().strftime('%B')  # Date format YYMMDD
```

`%B` produces a full month name (e.g., "January"), not YYMMDD. The comment is misleading.

---

## Test Coverage

There are **zero test files** in the entire codebase. Given that this pipeline performs destructive operations (truncating production tables), even basic integration tests or dry-run validations would significantly reduce risk.

---

## Summary of Priority Fixes

| Priority | Issue | Impact |
|----------|-------|--------|
| **Critical** | `enable_sde_edits` calls `startOperation()` instead of `stopOperation()` | Data corruption risk |
| **Critical** | `update_parcel_pt()` leaves single-point table empty after truncation | Missing data in production |
| **High** | Undefined variables in `prepare_prov_shapefiles()` scope | Runtime crash |
| **High** | Missing `metadata` module | Import failure |
| **High** | Misleading empty-table guards in `truncate_load_linns_all_rw()` / `load_linns_all()` | Blocks valid loads |
| **Medium** | Area validation logic is ineffective | Silent data quality issues |
| **Medium** | `input()` calls block automation | Can't run unattended |
| **Medium** | Hard-coded paths and SDE connections | Environment portability |
| **Medium** | Duplicated code across files | Maintenance burden |
| **Low** | Inconsistent logging mechanisms | Debugging difficulty |
| **Low** | No tests | Regression risk |
| **Low** | Stale comments, unused variables | Code clarity |
