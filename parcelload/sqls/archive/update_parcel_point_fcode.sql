UPDATE LND_parcel_point
SET fcode = 'CDPD'
WHERE fcode like 'CDPD%';

UPDATE LND_parcel_point
SET fcode = 'CDPIAR'
WHERE fcode like 'CDPIAR%';

UPDATE LND_parcel_point
SET fcode = 'CDPIR'
WHERE fcode IN ('CDPIR2','CDPIR6','CDPIR7');

UPDATE LND_parcel_point
SET fcode = 'CDPIRR'
WHERE fcode like 'CDPIRR%';

UPDATE LND_parcel_point
SET fcode = 'CDPU'
WHERE fcode like 'CDPU%';

UPDATE LND_parcel_point
SET fcode = 'CDPIWA'
WHERE fcode like 'CDPIWA%';

UPDATE LND_parcel_point
SET fcode = 'CDPIWL'
WHERE fcode like 'CDPIWL%';

UPDATE LND_parcel_point
SET fcode = 'CDPI'
WHERE fcode IN ('CDPI2','CDPI6','CDPI7','CDPI71');

UPDATE LND_parcel_point
SET fcode = 'CDPIUR'
WHERE fcode like 'CDPIUR%';

UPDATE LND_parcel_point
SET source = UPPER(source);

UPDATE LND_parcel_point
SET sacc = 'IN';

UPDATE LND_parcel_point
SET sdate = TO_DATE(operator,'YYYYMMDD');

commit;

UPDATE LND_parcel_point
SET operator = 'NSGC';

commit;
