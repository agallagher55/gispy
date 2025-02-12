TRUNCATE TABLE LND_parcel_point_old;
--CREATE TABLE LND_parcel_point_old AS
INSERT INTO LND_parcel_point_old(pid)
SELECT pid 
FROM LND_parcel_point;
commit;
