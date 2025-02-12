BEGIN TRANSACTION;

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPD'
WHERE fcode like 'CDPD%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIAR'
WHERE fcode like 'CDPIAR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIR'
WHERE fcode IN ('CDPIR2','CDPIR6','CDPIR7', 'CDPIR8');

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIRR'
WHERE fcode like 'CDPIRR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPU'
WHERE fcode like 'CDPU%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIWA'
WHERE fcode like 'CDPIWA%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIWL'
WHERE fcode like 'CDPIWL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPI'
WHERE fcode IN ('CDPI2','CDPI6','CDPI7','CDPI71');

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPIUR'
WHERE fcode like 'CDPIUR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_polygon]
SET fcode = 'CDPL'
WHERE fcode like 'CDPL%';

commit;



--SELECT fcode, count(fcode)
--FROM [GISRW01].[sdeadm].[LND_parcel_polygon]
--GROUP BY fcode
--ORDER BY fcode;

--SELECT sdate, count(sdate)
--FROM [GISRW01].[sdeadm].[LND_parcel_polygon]
--GROUP BY sdate
--ORDER BY sdate;


