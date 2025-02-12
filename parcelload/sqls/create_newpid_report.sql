SELECT DISTINCT pid
FROM [GISRW01].[sdeadm].[LND_parcel_point]
EXCEPT
SELECT DISTINCT pid
FROM [GISRW01].[sdeadm].[LND_parcel_point_old]
;