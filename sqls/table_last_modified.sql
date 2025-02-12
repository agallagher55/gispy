SELECT
    OBJECT_NAME(OBJECT_ID) AS TableName,
    last_user_update AS LastModifiedTime
FROM
    sys.dm_db_index_usage_stats
WHERE
    database_id = DB_ID() -- current database
    --AND OBJECT_ID = OBJECT_ID('TRN_STREET_DEAD_END')
ORDER BY
	TableName
    LastModifiedTime DESC;
