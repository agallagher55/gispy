
-----------------------------------------
-- Run a query to get the distinct pid values that are in LND_parcel_point but not in LND_parcel_point_old

BEGIN TRANSACTION;

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDIRB'
WHERE fcode like 'CDIRB%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDIRBMG'
WHERE fcode like 'CDIRBMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDIRRB'
WHERE fcode like 'CDIRRB%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDPL'
WHERE fcode like 'CDPL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDPLMG'
WHERE fcode like 'CDPLMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRAB'
WHERE fcode like 'CDRRAB%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRRD'
WHERE fcode like 'CDRRRD%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRRDCR'
WHERE fcode like 'CDRRRDCR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRRDMG'
WHERE fcode like 'CDRRRDMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRRDP'
WHERE fcode like 'CDRRRDP%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDRRRR'
WHERE fcode like 'CDRRRR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDST'
WHERE fcode like 'CDST%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDUN'
WHERE fcode like 'CDUN%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWAAB'
WHERE fcode like 'CDWAAB%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWACA'
WHERE fcode like 'CDWACA%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWACO'
WHERE fcode like 'CDWACO%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWADI'
WHERE fcode like 'CDWADI%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWAFU'
WHERE fcode like 'CDWAFU%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWAIS'
WHERE fcode like 'CDWAIS%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWALIS'
WHERE fcode like 'CDWALIS%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWALK'
WHERE fcode like 'CDWALK%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARS'
WHERE fcode like 'CDWARS%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVDL'
WHERE fcode like 'CDWARVDL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVDLMG'
WHERE fcode like 'CDWARVDLMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVIS'
WHERE fcode like 'CDWARVIS%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVLK'
WHERE fcode like 'CDWARVLK%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVSL'
WHERE fcode like 'CDWARVSL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVSLMG'
WHERE fcode like 'CDWARVSLMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WACO'
WHERE fcode like 'WACO%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WALK'
WHERE fcode like 'WALK%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARLDL'
WHERE fcode like 'WARVDL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARVIS'
WHERE fcode like 'WARVIS%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARVLK'
WHERE fcode like 'WARVLK%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARVSL'
WHERE fcode like 'WARVSL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARVSLMG'
WHERE fcode like 'WARVSLMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WARVSP'
WHERE fcode like 'WARVSP%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'DLMG'
WHERE fcode like 'DLMG%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWALL'
WHERE fcode like 'CDWALL%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'WASW'
WHERE fcode like 'WASW%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWARVSP'
WHERE fcode like 'CDWARVSP%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDPI'
WHERE fcode like 'CDPI%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDPIR'
WHERE fcode like 'CDPIR%';

UPDATE [GISRW01].[sdeadm].[LND_parcel_line]
SET fcode = 'CDWASW'
WHERE fcode like 'CDWASW%';

commit;

