# gispy — Claude Code Reference

ArcPy/ArcSDE automation scripts for Halifax Regional Municipality (HRM) GIS operations.

---

## Workflow

Tasks arrive as Jira tickets, emails, or chat messages. The user translates the
request into a `task.txt` (see convention below) and invokes Claude Code to
generate or modify the appropriate script.

**Typical invocations:**
- `"execute task.txt"` → read task.txt, generate a ready-to-run script
- `"review <file>.py for issues"` → audit and fix the script
- `"update task.txt with new fields and regenerate"` → update an existing script

---

## Operation type → example script mapping

| PyCharm template         | Example script                                  | Key variable(s)                          |
|--------------------------|-------------------------------------------------|------------------------------------------|
| GIS Field Schema         | `examples/fields/update_field_schema.py`        | `update_feature_info` dict               |
| GIS Add Fields           | `examples/fields/add_fields.py`                 | `new_field_info` dict                    |
| GIS Delete Fields        | `examples/fields/delete_fields.py`              | `UPDATE_FEATURE`, `delete_fields` list   |
| GIS Field Default        | `examples/fields/set_field_defaults.py`         | `FEATURE`, `FIELD_DEFAULTS` dict         |
| GIS Assign Domains       | `examples/domains/assign_field_domain.py`       | `DOMAIN_FIELD_INFO` dict                 |
| GIS Change Domain Values | `examples/domains/change_domain_values.py`      | domain name + values dict                |
| GIS Domains Report       | `examples/domains/domains_report.py`            | workspace / domain filter                |
| GIS New Feature          | `examples/new_feature.py`                       | `feature_config.ini`, SDSF Excel file   |
| GIS Retire Feature       | `retire_features.py`                            | feature list                             |
| GIS Enable Editor Tracking | `editor_tracking.py`                          | feature list                             |
| LRS - New Event Table    | `LRS/1_create_events.py`                        | event table config                       |

---

## Standard script patterns

### Feature class naming
- SDE format: `SDEADM.SCHEMA_tablename`  (e.g. `SDEADM.TRN_traffic_calming_assessm`)
- GDB format: strip schema prefix — `db.lower().endswith(".gdb")` → `name.split(".")[-1]`
- WEBGIS format: replace `SDEADM.` with `WEBGIS.`

### config.ini keys

```ini
[SERVER]          # used when COMPUTERNAME contains "APP" (server run)
dev_rw            # dev read-write SDE connection
dev_ro            # dev read-only SDE connection
dev_web_ro_gdb    # dev web read-only file GDB

qa_rw / qa_ro / qa_web_ro_gdb
prod_rw / prod_ro / prod_web_ro_gdb

[LOCAL]           # used otherwise (local dev run)
# same keys
```

`run_from = "SERVER" if "APP" in os.environ['COMPUTERNAME'] else "LOCAL"`

### Database loop idiom
```python
for dbs in [
    [config.get(run_from, "dev_rw")],       # uncomment others to extend
    # [config.get(run_from, "qa_rw")],
    # [config.get(run_from, "prod_rw")],
]:
    if dbs:
        for db in dbs:
            with arcpy.EnvManager(workspace=db):
                ...
```

### GDB name stripping (do this ONCE before the field loop, not inside it)
```python
feature = (
    feature_key.upper().replace("SDEADM.", "")
    if db.lower().endswith(".gdb")
    else feature_key
)
```

### Standard logging setup
```python
import logging, os, datetime
from configparser import ConfigParser

log_file = os.path.join(os.getcwd(), f"{datetime.date.today()}_<operation>.log")
logger = logging.getLogger('locators')
logger.setLevel(logging.DEBUG)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
log_formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | FUNCTION: %(funcName)s | Msgs: %(message)s',
    datefmt='%d-%b-%y %H:%M:%S'
)
file_handler.setFormatter(log_formatter)
console_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
```

### Exception handling pattern
```python
except arcpy.ExecuteError:
    logger.error(arcpy.GetMessages(2))
except Exception as e:
    logger.error(e)
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    logger.error("PYTHON ERRORS:\n" + tbinfo + "\n" + str(sys.exc_info()))
    logger.error("GP ERRORS:\n" + arcpy.GetMessages(2))
    sys.exit()
```

---

## task.txt convention

When a task arrives (Jira, email, chat), translate it into this YAML format in
`task.txt` before invoking Claude Code. See the full schema and examples in the
committed `task.txt` at the repo root.

**Minimal shape:**
```yaml
operation: <operation_type>   # see table above
feature: SDEADM.SCHEMA_tablename
databases: [dev_rw]           # expand to qa_rw, prod_rw when ready to promote
# operation-specific keys below...
notes: "Jira GIS-XXXX — one-line summary of why"
```

**Supported operation types:**
`update_field_schema`, `add_fields`, `delete_fields`, `set_field_defaults`,
`assign_domains`, `change_domain_values`, `new_domain`, `new_feature`,
`assign_editor_tracking`, `retire_feature`

---

## Key modules

| Module                              | Purpose                                           |
|-------------------------------------|---------------------------------------------------|
| `utils.py`                          | `setupLog()`, `arcpy_messages` decorator, helpers |
| `connections.py`                    | `connection_type(db)` → `("SDE"|"GDB", "RW"|"RO")` |
| `features.py`                       | Feature listing and dataframe conversion          |
| `domains.py`                        | `create_domain()`, `add_code_value()`             |
| `subtypes.py`                       | Subtype operations                                |
| `replicas/replicas.py`              | `add_to_replica()`                                |
| `SpatialDataSubmissionForms/`       | Excel SDSF parsing (`FieldsReport`, `DomainsReport`) |
