-- Create new table to identify condo PIDs, using linns_pidrelate
-- Get all condo PIDs that fall within the area rate

DROP TABLE AR_STORMWATER_CONDO_in_SAP;

CREATE TABLE AR_STORMWATER_CONDO_in_SAP 
AS (
    SELECT l.PID, l.PIDRELATE, l.RELNAME, a.arcode
    FROM AR_STORMWATER_pid_SAP a, linns_pidrelate l
    WHERE a.pid = l.pid AND 
		l.RELNAME = 'CONDO COMMON PARCEL'
);

commit;
--exit;