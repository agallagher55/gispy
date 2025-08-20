DECLARE @RoleName SYSNAME = '%POLICE%';  -- change this as needed

SELECT 
    dp.name AS DatabaseRole,
    SCHEMA_NAME(o.schema_id) AS SchemaName,
    o.name AS TableName,
    STRING_AGG(p.permission_name, ', ') 
        WITHIN GROUP (ORDER BY p.permission_name) AS Permissions
FROM sys.database_permissions p
JOIN sys.objects o
    ON p.major_id = o.object_id
JOIN sys.database_principals dp
    ON p.grantee_principal_id = dp.principal_id
WHERE dp.name LIKE @RoleName
  AND o.type = 'U'
  -- exclude Esri delta/archive tables
  AND o.name NOT LIKE 'A[0-9]%'
  AND o.name NOT LIKE 'D[0-9]%'
  AND o.name NOT LIKE 'H[0-9]%'
  -- exclude system/internal tables
  AND o.name NOT LIKE 'SDE[_]%'
  AND o.name NOT LIKE 'GDB[_]%'
  -- exclude Esri auxiliary tables like T_#_xxx
  AND o.name NOT LIKE 'T_[0-9]_%'
GROUP BY dp.name, SCHEMA_NAME(o.schema_id), o.name
ORDER BY SchemaName, TableName;
