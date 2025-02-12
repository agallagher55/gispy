TRUNCATE TABLE PID_OWNER;
commit;
INSERT INTO PID_OWNER(acctno,last_name,first_name,middle_name,enterprise_name,pid,propclass,f_address1,f_address2,community,prov_state,country,postal_code)
SELECT acctno,last_name,first_name,middle_name,enterprise_name,pid,propclass,f_address1,f_address2,community,prov_state,country,postal_code
FROM  PID_OWNER@FROM_SDE;
commit;
exit;
