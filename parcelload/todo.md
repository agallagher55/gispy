# LINNS_ALL SQL

---

## 🔴 High Priority

**1. `RANK()` instead of `ROW_NUMBER()` — risk of duplicate output rows**

`RANK()` assigns the same rank to ties. If two owners on the same PID produce an identical `owner_full` string (e.g. two people named "Smith, John"), both get `PID_FIRSTOWNER_RANK = 1`. The final `JOIN` between `F` and `L` then produces a Cartesian product for that PID — silent row duplication in the output. `ROW_NUMBER()` would guarantee exactly one row per PID per side.

---

**2. The `RANK()` ORDER BY doesn't match `owner_full`'s logic**

`owner_full` is built using this logic:
```sql
CASE WHEN enterprise_name IS NULL OR TRIM(enterprise_name) = ''
    THEN <name concatenation>
    ELSE TRIM(enterprise_name)
END
```

But both `RANK()` expressions order by only the **name concatenation** — `enterprise_name` is completely absent from the `ORDER BY`. So for enterprise-owned parcels, the ranking is based on `last_name` (which could be `NULL`), not the actual `enterprise_name`. The "first" and "last" owners selected may not correspond to alphabetical order of the `owner_full` values that end up in the output. The `ORDER BY` should mirror the `CASE` expression in `owner_full`.

---

## 🟡 Medium Priority

**3. The outer `COALESCE` in `owner_full` and the `RANK()` ORDER BY is dead code**

The comment says the second `COALESCE` branch handles the case where `middle_name` is NULL — but the inner `COALESCE(' ' + TRIM(middle_name), '')` already handles that by returning `''` instead of `NULL`. The outer fallback branch is only ever reached when `last_name` itself is `NULL`, in which case the fallback expression *also* evaluates to `NULL` (since it still starts with `TRIM(last_name)`). The second branch never produces a different result than the first. It can be simplified to:

```sql
TRIM(last_name) 
    + COALESCE(', ' + TRIM(first_name), '')
    + COALESCE(' ' + TRIM(middle_name), '')
```

---

**4. `FULL_LINNS_LIST` CTE is evaluated twice**

The final `SELECT` references `FULL_LINNS_LIST` twice — once filtered to `PID_FIRSTOWNER_RANK = 1` (as `F`) and once to `PID_LASTOWNER_RANK = 1` (as `L`). SQL Server CTEs are not materialized by default, so this complex CTE (with four joins and two window functions) likely runs twice. Materializing it into a `#temp` table first would be both safer and faster:

```sql
SELECT * INTO #full_linns FROM FULL_LINNS_LIST;
-- then reference #full_linns in the final SELECT
```

---

**5. `TYPE` field depends on which owner record surfaces as "first"**

`propclass` lives on the owner record in `PID_owner`, not directly on the parcel. `TYPE` is taken from the `F` (first-ranked owner) record. If owners on the same PID have different `propclass` values, the result is arbitrary and dependent on sort order. If `propclass` is truly a parcel-level attribute, it would be cleaner to join it directly from a parcel-level source rather than relying on an owner record.

---

## 🟢 Lower Priority / Style

**6. `SELECT INTO` vs. explicit `CREATE TABLE`**

`SELECT INTO` infers column types from the query — you get no control over nullability, collation, or indexes. If the query changes subtly, the output schema can drift silently. An explicit `CREATE TABLE` with defined types, followed by `INSERT INTO ... SELECT`, is more robust for a production staging table.

**7. The "highest AAN" assumption should be documented**

```sql
RANK() OVER (PARTITION BY PID ORDER BY AAN DESC) -- highest AAN per PID
```

This is a meaningful business logic decision (last/highest AAN wins). The comment acknowledges it, which is good — but it's worth confirming this is always the right AAN to join assessment data against, especially if AANs are reassigned or there are correction accounts.

**8. `OWNER2` is alphabetically last, not "second"**

With 3+ owners on a PID, `OWNER2` will be the alphabetically last owner, skipping anyone in between. If the intent is truly "show up to two owners," this works fine as a display shorthand — but it's worth being explicit in documentation that this is alphabetical first/last, not positional first/second.

---

## Summary Table

| # | Issue | Risk |
|---|---|---|
| 1 | `RANK()` allows ties → duplicate output rows | High |
| 2 | `RANK()` ORDER BY excludes `enterprise_name` | High |
| 3 | `ASSESSMENT_LOOKUP DISTINCT` doesn't deduplicate ACCTNO | High |
| 4 | Dead code in outer `COALESCE` | Low (correctness ok, just confusing) |
| 5 | CTE evaluated twice | Medium (performance) |
| 6 | `TYPE` from owner record, not parcel | Medium |
| 7 | `SELECT INTO` schema drift risk | Low |
| 8 | Highest-AAN assumption undocumented | Low |
| 9 | OWNER2 = alphabetically last, not 2nd | Low |
