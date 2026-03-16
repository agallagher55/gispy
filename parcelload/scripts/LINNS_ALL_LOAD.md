# LINNS_ALL_STAGE — SQL Input/Output Documentation

---

## Output Table

**`[sdeadm].[LINNS_ALL_STAGE]`**

| Output Field | Source Table(s) | Source Field(s) | Logic / Notes |
|---|---|---|---|
| `PID` | `sdeadm.LND_parcel_polygon` | `pid` | Base parcel identifier; rows where `pid = '00000000'` or `pid = ' '` are excluded |
| `AAN` | `sdeadm.LINNS_pidaantax` | `aan` | Highest (last) AAN per PID, selected via `RANK() … ORDER BY AAN DESC` |
| `ASSESSMENT` | `HANSENDATA.ACCTASR` | `asdtaxable` | Joined on `AAN = ACCTNO`; aliased as `ASSESSMENT` |
| `AREAUNITS` | `sdeadm.LINNS_PIDMSTRS` | `area`, `area_unit` | Numeric area concatenated with a spelled-out unit label (e.g. `"1.5 Acres"`); aliased as `AREAUNITS` |
| `OWNER1` | `sdeadm.PID_owner` | `last_name`, `first_name`, `middle_name`, `enterprise_name` | **First** owner alphabetically per PID (`PID_FIRSTOWNER_RANK = 1`). Set to `NULL` for condos and mobile homes |
| `OWNER2` | `sdeadm.PID_owner` | `last_name`, `first_name`, `middle_name`, `enterprise_name` | **Last** owner alphabetically per PID (`PID_LASTOWNER_RANK = 1`). Set to `NULL` for condos/mobile homes; also `NULL` when `OWNER1 = OWNER2` (single owner) |
| `TYPE` | `sdeadm.PID_owner` | `propclass` | `'PROVINCIAL'` if `propclass` contains `'PROV'`; `'FEDERAL'` if contains `'FED'`; otherwise `NULL`. Taken from the first owner record |

---

## Input Tables

### Direct Sources

| Table | Schema | Database | Role |
|---|---|---|---|
| `LND_parcel_polygon` | `sdeadm` | GISRW01 | Base list of all parcels; provides `PID` |
| `LINNS_PIDMSTRS` | `sdeadm` | GISRW01 | Parcel master attributes: `area`, `area_unit`, `parceltype` |
| `PID_owner` | `sdeadm` | GISRW01 | Owner name fields: `last_name`, `first_name`, `middle_name`, `enterprise_name`, `propclass` |
| `LINNS_pidaantax` | `sdeadm` | GISRW01 | PID-to-AAN crosswalk; multiple AANs per PID possible |
| `ACCTASR` | `HANSENDATA` | Hansen | Account/assessment data: `acctno`, `asdtaxable`, `acctsubgrp`, `acctkey` |
| `pidgrid` | `HANSENDATA` | Hansen | PID-to-account crosswalk: `prclid`, `acctkey` |

---

## Intermediate CTEs

| CTE Name | Purpose | Key Fields |
|---|---|---|
| `CONDO_PID_LOOKUP` | Identifies condo unit PIDs | `pid` from `LINNS_PIDMSTRS` where `parceltype = 'CC'` |
| `MOBILE_HOME_PID_LOOKUP` | Identifies mobile home PIDs via Hansen | `pid` (`prclid`) from `HANSENDATA.pidgrid`; filtered to accounts with `acctsubgrp = 'MOBL'`, then joined back to `acctsubgrp = 'REG'` records |
| `ASSESSMENT_LOOKUP` | Distinct taxable assessments | `acctno`, `asdtaxable` from `HANSENDATA.ACCTASR` |
| `FULL_LINNS_LIST` | Full denormalized parcel + owner list with ranking | Joins all `sdeadm` tables; computes `owner_full`, `PID_FIRSTOWNER_RANK`, `PID_LASTOWNER_RANK`, `area2`, `type` |

---

## Owner Name Construction (`owner_full`)

Built inside `FULL_LINNS_LIST`, used to populate `OWNER1` and `OWNER2`:

```
IF enterprise_name IS NULL or empty:
    owner_full = TRIM(last_name) + ', ' + TRIM(first_name) + ' ' + TRIM(middle_name)
    (NULL name parts are omitted cleanly via COALESCE)
ELSE:
    owner_full = TRIM(enterprise_name)
```

---

## Condo / Mobile Home Suppression

A combined exclusion list is built from `CONDO_PID_LOOKUP` and `MOBILE_HOME_PID_LOOKUP` (via `UNION`). Any PID found in this list results in `OWNER1 = NULL` and `OWNER2 = NULL` in the output — owner identity is intentionally withheld for these parcel types.

---

## Key Joins Summary

```
LND_parcel_polygon (base)
  LEFT JOIN  LINNS_PIDMSTRS          ON pid         → area, area_unit
  LEFT JOIN  PID_owner               ON pid         → name fields, propclass
  LEFT JOIN  LINNS_pidaantax         ON pid         → aan (highest rank only)
  LEFT JOIN  ACCTASR (via CTE)       ON aan=acctno  → asdtaxable
  LEFT JOIN  Condo+MobileHome list   ON pid         → suppresses owner fields
```
