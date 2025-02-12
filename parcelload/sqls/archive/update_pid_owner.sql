--DROP TABLE TMP_PARCEL_CUSTOMER;
--CREATE TABLE TMP_PARCEL_CUSTOMER AS
TRUNCATE TABLE PID_OWNER;
commit;
INSERT INTO PID_OWNER(acctno,last_name,first_name,middle_name,enterprise_name,pid,propclass,f_address1,f_address2,community,prov_state,country,postal_code)
SELECT c.acctno,c.last_name,c.first_name,c.middle_name,c.enterprise_name,t.pid,c.propclass,f_address1,f_address2,community,prov_state,country,postal_code
FROM  custadm.account_owner@&1 c, lnd_hansen_tax t
WHERE c.acctno = t.acctno(+);
commit;
exit;
