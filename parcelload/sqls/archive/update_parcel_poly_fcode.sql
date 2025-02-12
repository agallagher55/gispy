UPDATE LND_parcel_polygon
SET fcode = 'CDPD'
WHERE fcode like 'CDPD%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPIAR'
WHERE fcode like 'CDPIAR%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPIR'
WHERE fcode IN ('CDPIR2','CDPIR6','CDPIR7');

UPDATE LND_parcel_polygon
SET fcode = 'CDPIRR'
WHERE fcode like 'CDPIRR%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPU'
WHERE fcode like 'CDPU%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPIWA'
WHERE fcode like 'CDPIWA%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPIWL'
WHERE fcode like 'CDPIWL%';

UPDATE LND_parcel_polygon
SET fcode = 'CDPI'
WHERE fcode IN ('CDPI2','CDPI6','CDPI7','CDPI71');

UPDATE LND_parcel_polygon
SET fcode = 'CDPIUR'
WHERE fcode like 'CDPIUR%';

--UPDATE LND_parcel_polygon
--SET source = UPPER(source);

--UPDATE LND_parcel_polygon
--SET sacc = 'DG';

--UPDATE LND_parcel_polygon
--SET sdate = TO_DATE(operator,'YYYYMMDD');

commit;

--UPDATE LND_parcel_polygon
--SET operator = 'NSGC';

commit;

SELECT fcode, count(fcode)
FROM LND_parcel_polygon
GROUP BY fcode
ORDER BY fcode;

SELECT sdate, count(sdate)
FROM LND_parcel_polygon
GROUP BY sdate
ORDER BY sdate;

exit
