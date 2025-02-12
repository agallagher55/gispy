-- Create new table by joining to linns_pidaantax, getting AANs for each PID
-- Remove any records with a null AAN

DROP TABLE AR_STORMWATER_AAN_SAP;

CREATE TABLE AR_STORMWATER_AAN_SAP AS
(
	SELECT TRIM(l.AAN) as "ACCTNO", a.PID, a.arcode
    FROM AR_STORMWATER_pid_SAP a, LINNS_PIDAANTAX l
    WHERE a.pid = l.pid
);

commit;

DELETE FROM AR_STORMWATER_AAN_SAP
WHERE ACCTNO IS NULL;

commit;
