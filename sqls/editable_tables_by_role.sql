SELECT 
    dp.name AS DatabaseRole,
    o.name AS TableName,
    STRING_AGG(p.permission_name, ', ') 
        WITHIN GROUP (ORDER BY p.permission_name) AS Permissions
FROM sys.database_permissions p
JOIN sys.objects o
    ON p.major_id = o.object_id
JOIN sys.database_principals dp
    ON p.grantee_principal_id = dp.principal_id
WHERE --dp.name LIKE @RoleName AND 
	o.type = 'U'

  -- exclude Esri delta/archive tables
  AND o.name NOT LIKE 'A[0-9]%'
  AND o.name NOT LIKE 'D[0-9]%'
  AND o.name NOT LIKE '%_H[0-9]'
  AND o.name NOT LIKE '%_H'
  AND o.name NOT LIKE 'N_[0-9]%'

  -- exclude system/internal tables
  AND o.name NOT LIKE 'SDE[_]%'
  AND o.name NOT LIKE 'GDB[_]%'

  -- exclude Esri auxiliary tables like T_#_xxx
  AND o.name NOT LIKE 'T_[0-9]_%'

  --AND p.permission_name LIKE '%,%'
  AND dp.name LIKE 'HRM%' AND dp.name NOT IN ('HRM\GIS_HW_ARCGIS_HRMBASIC', 'HRM_CITYWORKS_USER') 
  AND dp.name NOT LIKE '%READER%' AND dp.name NOT LIKE '%VIEWER%'

GROUP BY dp.name, SCHEMA_NAME(o.schema_id), o.name
ORDER BY DatabaseRole, TableName
;
