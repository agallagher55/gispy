UPDATE LND_parcel_line
SET fcode = 'CDIRB'
WHERE fcode like 'CDIRB%';

UPDATE LND_parcel_line
SET fcode = 'CDIRBMG'
WHERE fcode like 'CDIRBMG%';

UPDATE LND_parcel_line
SET fcode = 'CDIRRB'
WHERE fcode like 'CDIRRB%';

UPDATE LND_parcel_line
SET fcode = 'CDPL'
WHERE fcode like 'CDPL%';

UPDATE LND_parcel_line
SET fcode = 'CDPLMG'
WHERE fcode like 'CDPLMG%';

UPDATE LND_parcel_line
SET fcode = 'CDRRAB'
WHERE fcode like 'CDRRAB%';

UPDATE LND_parcel_line
SET fcode = 'CDRRRD'
WHERE fcode like 'CDRRRD%';

UPDATE LND_parcel_line
SET fcode = 'CDRRRDCR'
WHERE fcode like 'CDRRRDCR%';

UPDATE LND_parcel_line
SET fcode = 'CDRRRDMG'
WHERE fcode like 'CDRRRDMG%';

UPDATE LND_parcel_line
SET fcode = 'CDRRRDP'
WHERE fcode like 'CDRRRDP%';

UPDATE LND_parcel_line
SET fcode = 'CDRRRR'
WHERE fcode like 'CDRRRR%';

UPDATE LND_parcel_line
SET fcode = 'CDST'
WHERE fcode like 'CDST%';

UPDATE LND_parcel_line
SET fcode = 'CDUN'
WHERE fcode like 'CDUN%';

UPDATE LND_parcel_line
SET fcode = 'CDWAAB'
WHERE fcode like 'CDWAAB%';

UPDATE LND_parcel_line
SET fcode = 'CDWACA'
WHERE fcode like 'CDWACA%';

UPDATE LND_parcel_line
SET fcode = 'CDWACO'
WHERE fcode like 'CDWACO%';

UPDATE LND_parcel_line
SET fcode = 'CDWADI'
WHERE fcode like 'CDWADI%';

UPDATE LND_parcel_line
SET fcode = 'CDWAFU'
WHERE fcode like 'CDWAFU%';

UPDATE LND_parcel_line
SET fcode = 'CDWAIS'
WHERE fcode like 'CDWAIS%';

UPDATE LND_parcel_line
SET fcode = 'CDWALIS'
WHERE fcode like 'CDWALIS%';

UPDATE LND_parcel_line
SET fcode = 'CDWALK'
WHERE fcode like 'CDWALK%';

UPDATE LND_parcel_line
SET fcode = 'CDWARS'
WHERE fcode like 'CDWARS%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVDL'
WHERE fcode like 'CDWARVDL%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVDLMG'
WHERE fcode like 'CDWARVDLMG%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVIS'
WHERE fcode like 'CDWARVIS%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVLK'
WHERE fcode like 'CDWARVLK%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVSL'
WHERE fcode like 'CDWARVSL%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVSLMG'
WHERE fcode like 'CDWARVSLMG%';

UPDATE LND_parcel_line
SET fcode = 'WACO'
WHERE fcode like 'WACO%';

UPDATE LND_parcel_line
SET fcode = 'WALK'
WHERE fcode like 'WALK%';

UPDATE LND_parcel_line
SET fcode = 'WARLDL'
WHERE fcode like 'WARVDL%';

UPDATE LND_parcel_line
SET fcode = 'WARVIS'
WHERE fcode like 'WARVIS%';

UPDATE LND_parcel_line
SET fcode = 'WARVLK'
WHERE fcode like 'WARVLK%';

UPDATE LND_parcel_line
SET fcode = 'WARVSL'
WHERE fcode like 'WARVSL%';

UPDATE LND_parcel_line
SET fcode = 'WARVSLMG'
WHERE fcode like 'WARVSLMG%';

UPDATE LND_parcel_line
SET fcode = 'WARVSP'
WHERE fcode like 'WARVSP%';

UPDATE LND_parcel_line
SET fcode = 'DLMG'
WHERE fcode like 'DLMG%';

UPDATE LND_parcel_line
SET fcode = 'CDWALL'
WHERE fcode like 'CDWALL%';

UPDATE LND_parcel_line
SET fcode = 'WASW'
WHERE fcode like 'WASW%';

UPDATE LND_parcel_line
SET fcode = 'CDWARVSP'
WHERE fcode like 'CDWARVSP%';

UPDATE LND_parcel_line
SET fcode = 'CDPI'
WHERE fcode like 'CDPI%';

UPDATE LND_parcel_line
SET fcode = 'CDPIR'
WHERE fcode like 'CDPIR%';

UPDATE LND_parcel_line
SET fcode = 'CDWASW'
WHERE fcode like 'CDWASW%';


--UPDATE LND_parcel_line
--SET source = 'LIC-PROPMAP';

--UPDATE LND_parcel_line
--SET sacc = 'DG';

--UPDATE LND_parcel_line
--SET sdate = (SELECT SYSDATE FROM DUAL);

--UPDATE LND_parcel_line
--SET operator = 'NSGC';

commit;

exit
