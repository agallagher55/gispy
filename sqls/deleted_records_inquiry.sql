SET NOCOUNT ON;

DECLARE @owner    sysname        = N'sdeadm';       -- schema / owner
DECLARE @table    sysname        = N'TRN_SECTRAV';  -- business table
DECLARE @id_field sysname        = N'TR_ID';        -- ID field
DECLARE @id_value nvarchar(4000) = N'TR1001095';    -- ID value

DECLARE @regid int;
DECLARE @base  nvarchar(517);
DECLARE @hist  nvarchar(517);
DECLARE @a     nvarchar(517);
DECLARE @d     nvarchar(517);

DECLARE @h_exists bit = 0;
DECLARE @base_has_globalid bit = 0;
DECLARE @a_has_globalid    bit = 0;
DECLARE @h_has_globalid    bit = 0;

DECLARE @q_id_field nvarchar(300);
DECLARE @base_globalid_expr nvarchar(200);
DECLARE @a_globalid_expr    nvarchar(200);
DECLARE @h_globalid_expr    nvarchar(200);
DECLARE @hist_rows_cte      nvarchar(max);
DECLARE @latest_hist_cte    nvarchar(max);
DECLARE @sql                nvarchar(max);

SELECT @regid = r.registration_id
FROM sde.SDE_table_registry r
WHERE UPPER(r.owner) = UPPER(@owner)
  AND UPPER(r.table_name) = UPPER(@table);

IF @regid IS NULL
BEGIN
    THROW 50000, 'Could not find registration_id for the supplied owner/table.', 1;
END;

SET @base = QUOTENAME(@owner) + N'.' + QUOTENAME(@table);
SET @hist = QUOTENAME(@owner) + N'.' + QUOTENAME(@table + N'_H');
SET @a    = QUOTENAME(@owner) + N'.' + QUOTENAME(N'a' + CONVERT(varchar(20), @regid));
SET @d    = QUOTENAME(@owner) + N'.' + QUOTENAME(N'd' + CONVERT(varchar(20), @regid));

IF OBJECT_ID(@base, 'U') IS NULL
BEGIN
    THROW 50001, 'Base table does not exist.', 1;
END;

IF OBJECT_ID(@a, 'U') IS NULL OR OBJECT_ID(@d, 'U') IS NULL
BEGIN
    THROW 50002, 'Adds or deletes table does not exist. Confirm the class is traditionally versioned.', 1;
END;

IF NOT EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(@base)
      AND name = @id_field
)
BEGIN
    THROW 50003, 'The supplied ID field does not exist on the base table.', 1;
END;

SET @h_exists = CASE WHEN OBJECT_ID(@hist, 'U') IS NOT NULL THEN 1 ELSE 0 END;

IF EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(@base)
      AND name = N'GLOBALID'
)
    SET @base_has_globalid = 1;

IF EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(@a)
      AND name = N'GLOBALID'
)
    SET @a_has_globalid = 1;

IF @h_exists = 1
AND EXISTS (
    SELECT 1
    FROM sys.columns
    WHERE object_id = OBJECT_ID(@hist)
      AND name = N'GLOBALID'
)
    SET @h_has_globalid = 1;

SET @q_id_field = QUOTENAME(@id_field);

SET @base_globalid_expr = CASE
    WHEN @base_has_globalid = 1 THEN N'CONVERT(nvarchar(40), [GLOBALID])'
    ELSE N'CAST(NULL AS nvarchar(40))'
END;

SET @a_globalid_expr = CASE
    WHEN @a_has_globalid = 1 THEN N'CONVERT(nvarchar(40), [GLOBALID])'
    ELSE N'CAST(NULL AS nvarchar(40))'
END;

SET @h_globalid_expr = CASE
    WHEN @h_has_globalid = 1 THEN N'CONVERT(nvarchar(40), [GLOBALID])'
    ELSE N'CAST(NULL AS nvarchar(40))'
END;

SET @hist_rows_cte = CASE
    WHEN @h_exists = 1 THEN
        N'
hist_rows AS (
    SELECT
        OBJECTID,
        CONVERT(nvarchar(4000), ' + @q_id_field + N') AS business_id,
        ' + @h_globalid_expr + N' AS globalid
    FROM ' + @hist + N'
    WHERE CONVERT(nvarchar(4000), ' + @q_id_field + N') = @id_value
),'
    ELSE
        N'
hist_rows AS (
    SELECT
        CAST(NULL AS int) AS OBJECTID,
        CAST(NULL AS nvarchar(4000)) AS business_id,
        CAST(NULL AS nvarchar(40)) AS globalid
    WHERE 1 = 0
),'
END;

SET @latest_hist_cte = CASE
    WHEN @h_exists = 1 THEN
        N'
latest_hist AS (
    SELECT TOP (1)
        h.GDB_FROM_DATE,
        h.GDB_TO_DATE,
        h.GDB_ARCHIVE_OID
    FROM ' + @hist + N' h
    WHERE CONVERT(nvarchar(4000), h.' + @q_id_field + N') = @id_value
    ORDER BY h.GDB_FROM_DATE DESC, h.GDB_ARCHIVE_OID DESC
),
latest_hist_single AS (
    SELECT
        MAX(GDB_FROM_DATE) AS latest_gdb_from_date,
        MAX(GDB_TO_DATE)   AS latest_gdb_to_date
    FROM latest_hist
),'
    ELSE
        N'
latest_hist_single AS (
    SELECT
        CAST(NULL AS datetime2(7)) AS latest_gdb_from_date,
        CAST(NULL AS datetime2(7)) AS latest_gdb_to_date
),'
END;

SET @sql = N'
;WITH
base_rows AS (
    SELECT
        OBJECTID,
        CONVERT(nvarchar(4000), ' + @q_id_field + N') AS business_id,
        ' + @base_globalid_expr + N' AS globalid
    FROM ' + @base + N'
    WHERE CONVERT(nvarchar(4000), ' + @q_id_field + N') = @id_value
),
' + @hist_rows_cte + N'
' + @latest_hist_cte + N'
add_rows AS (
    SELECT
        OBJECTID,
        SDE_STATE_ID,
        CONVERT(nvarchar(4000), ' + @q_id_field + N') AS business_id,
        ' + @a_globalid_expr + N' AS globalid
    FROM ' + @a + N'
    WHERE CONVERT(nvarchar(4000), ' + @q_id_field + N') = @id_value
),
delete_hits AS (
    SELECT DISTINCT
        COALESCE(a.business_id, b.business_id, h.business_id) AS business_id,
        COALESCE(a.globalid, b.globalid, h.globalid) AS globalid,
        CASE
            WHEN a.OBJECTID IS NOT NULL
             AND a.SDE_STATE_ID = d.SDE_STATE_ID
                THEN ''matched_add_row''
            WHEN b.OBJECTID IS NOT NULL
                THEN ''matched_base_objectid''
            WHEN h.OBJECTID IS NOT NULL
                THEN ''matched_archive_objectid''
            ELSE ''unresolved''
        END AS match_type,
        d.SDE_DELETES_ROW_ID,
        d.SDE_STATE_ID AS row_state_id,
        d.DELETED_AT   AS delete_state_id
    FROM ' + @d + N' d
    LEFT JOIN add_rows a
        ON a.OBJECTID = d.SDE_DELETES_ROW_ID
       AND a.SDE_STATE_ID = d.SDE_STATE_ID
    LEFT JOIN base_rows b
        ON b.OBJECTID = d.SDE_DELETES_ROW_ID
    LEFT JOIN hist_rows h
        ON h.OBJECTID = d.SDE_DELETES_ROW_ID
    WHERE a.OBJECTID IS NOT NULL
       OR b.OBJECTID IS NOT NULL
       OR h.OBJECTID IS NOT NULL
),
version_roots AS (
    SELECT
        v.owner AS version_owner,
        v.name  AS version_name,
        v.state_id AS version_current_state_id
    FROM sde.SDE_versions v
),
version_lineage AS (
    SELECT
        vr.version_owner,
        vr.version_name,
        vr.version_current_state_id,
        s.state_id,
        s.parent_state_id,
        0 AS depth
    FROM version_roots vr
    JOIN sde.SDE_states s
        ON s.state_id = vr.version_current_state_id

    UNION ALL

    SELECT
        vl.version_owner,
        vl.version_name,
        vl.version_current_state_id,
        s.state_id,
        s.parent_state_id,
        vl.depth + 1
    FROM version_lineage vl
    JOIN sde.SDE_states s
        ON s.state_id = vl.parent_state_id
    WHERE vl.parent_state_id IS NOT NULL
      AND vl.parent_state_id <> vl.state_id
),
scored_matches AS (
    SELECT
        @owner AS owner_name,
        @table AS table_name,
        @id_field AS id_field,
        @id_value AS id_value,
        dh.business_id,
        dh.globalid,
        dh.match_type,
        dh.SDE_DELETES_ROW_ID,
        dh.row_state_id,
        dh.delete_state_id,
        ds.creation_time AS delete_state_created,
        lhs.latest_gdb_to_date,
        vl.version_owner,
        vl.version_name,
        vl.version_current_state_id,
        vl.depth AS hops_from_current_version_state,
        CASE
            WHEN vl.version_name IS NOT NULL
                THEN QUOTENAME(vl.version_owner) + ''.'' + vl.version_name
            ELSE NULL
        END AS best_match_version,
        CASE
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth = 0 THEN ''highest''
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth IS NOT NULL THEN ''high''
            WHEN dh.match_type IN (''matched_base_objectid'', ''matched_archive_objectid'') AND vl.depth = 0 THEN ''medium_high''
            WHEN dh.match_type IN (''matched_base_objectid'', ''matched_archive_objectid'') AND vl.depth IS NOT NULL THEN ''medium''
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth IS NULL THEN ''medium''
            ELSE ''low''
        END AS match_quality,
        CASE
            WHEN lhs.latest_gdb_to_date IS NOT NULL
             AND lhs.latest_gdb_to_date < ''9999-12-31''
                THEN lhs.latest_gdb_to_date
            WHEN ds.creation_time IS NOT NULL
                THEN ds.creation_time
            ELSE NULL
        END AS likely_deleted_at,
        CASE
            WHEN lhs.latest_gdb_to_date IS NOT NULL
             AND lhs.latest_gdb_to_date < ''9999-12-31''
                THEN ''archive GDB_TO_DATE''
            WHEN ds.creation_time IS NOT NULL
                THEN ''delete state creation_time''
            ELSE ''no timing evidence found''
        END AS likely_deleted_basis,
        CASE
            WHEN lhs.latest_gdb_to_date IS NOT NULL
             AND lhs.latest_gdb_to_date < ''9999-12-31''
             AND vl.depth = 0
                THEN ''archive shows the record ended then, and delete_state_id exactly matches the current state of this version''
            WHEN lhs.latest_gdb_to_date IS NOT NULL
             AND lhs.latest_gdb_to_date < ''9999-12-31''
             AND vl.depth IS NOT NULL
                THEN ''archive shows the record ended then, and this version descends from the delete_state_id''
            WHEN lhs.latest_gdb_to_date IS NOT NULL
             AND lhs.latest_gdb_to_date < ''9999-12-31''
                THEN ''archive shows the record ended then''
            WHEN vl.depth = 0
                THEN ''delete_state_id exactly matches the current state of this version''
            WHEN vl.depth IS NOT NULL
                THEN ''this version descends from the delete_state_id through state ancestry''
            WHEN dh.match_type = ''matched_add_row''
                THEN ''strong delete-table linkage was found, but no current version lineage match remains''
            ELSE ''delete-table evidence was found, but version linkage is weaker or no longer present''
        END AS why_it_matched,
        CASE
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth = 0 THEN 1
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth IS NOT NULL THEN 2
            WHEN dh.match_type IN (''matched_base_objectid'', ''matched_archive_objectid'') AND vl.depth = 0 THEN 3
            WHEN dh.match_type IN (''matched_base_objectid'', ''matched_archive_objectid'') AND vl.depth IS NOT NULL THEN 4
            WHEN dh.match_type = ''matched_add_row'' AND vl.depth IS NULL THEN 5
            ELSE 6
        END AS sort_rank
    FROM delete_hits dh
    LEFT JOIN version_lineage vl
        ON vl.state_id = dh.delete_state_id
    LEFT JOIN sde.SDE_states ds
        ON ds.state_id = dh.delete_state_id
    CROSS JOIN latest_hist_single lhs
),
fallback_row AS (
    SELECT
        @owner AS owner_name,
        @table AS table_name,
        @id_field AS id_field,
        @id_value AS id_value,
        CONVERT(nvarchar(4000), @id_value) AS business_id,
        CAST(NULL AS nvarchar(40)) AS globalid,
        CAST(NULL AS nvarchar(50)) AS match_type,
        CAST(NULL AS int) AS SDE_DELETES_ROW_ID,
        CAST(NULL AS int) AS row_state_id,
        CAST(NULL AS int) AS delete_state_id,
        CAST(NULL AS datetime2(7)) AS delete_state_created,
        CAST(NULL AS datetime2(7)) AS latest_gdb_to_date,
        CAST(NULL AS nvarchar(255)) AS version_owner,
        CAST(NULL AS nvarchar(255)) AS version_name,
        CAST(NULL AS int) AS version_current_state_id,
        CAST(NULL AS int) AS hops_from_current_version_state,
        CAST(NULL AS nvarchar(300)) AS best_match_version,
        ''none'' AS match_quality,
        CAST(NULL AS datetime2(7)) AS likely_deleted_at,
        ''no timing evidence found'' AS likely_deleted_basis,
        ''No linked delete-table record was found for the supplied ID.'' AS why_it_matched,
        999 AS sort_rank
    WHERE NOT EXISTS (SELECT 1 FROM delete_hits)
)
SELECT TOP (1)
    owner_name,
    table_name,
    id_field,
    id_value,
    business_id,
    globalid,
    best_match_version,
    version_owner,
    version_name,
    version_current_state_id,
    match_quality,
    likely_deleted_at,
    likely_deleted_basis,
    delete_state_created,
    latest_gdb_to_date AS archive_latest_gdb_to_date,
    why_it_matched,
    match_type,
    SDE_DELETES_ROW_ID,
    row_state_id,
    delete_state_id,
    hops_from_current_version_state
FROM (
    SELECT * FROM scored_matches
    UNION ALL
    SELECT * FROM fallback_row
) q
ORDER BY
    sort_rank,
    likely_deleted_at DESC,
    delete_state_id DESC,
    row_state_id DESC,
    hops_from_current_version_state,
    version_owner,
    version_name
OPTION (MAXRECURSION 32767);
';

EXEC sys.sp_executesql
    @stmt = @sql,
    @params = N'@owner sysname,
                @table sysname,
                @id_field sysname,
                @id_value nvarchar(4000)',
    @owner    = @owner,
    @table    = @table,
    @id_field = @id_field,
    @id_value = @id_value;
