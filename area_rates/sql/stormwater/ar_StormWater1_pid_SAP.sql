-- The new table is created as a result of a SELECT query that retrieves pid and AREARATE_CODE columns 
-- from the SAP_storm_water table, but only for rows that have the highest shape_area value within each pid group.

-- The SELECT query first groups the rows in the SAP_storm_water table by pid, then for each group, 
-- it selects the row with the maximum shape_area value using the MAX function. 
-- The IN operator is then used to filter the SAP_storm_water table, keeping only the rows that have a pid and 
-- shape_area combination that appears in the subquery.

-- Finally, the resulting rows are used to populate the new AR_STORMWATER_pid_SAP table, 
-- which is created with the same column names as the selected columns in the SELECT query. 
-- The AS keyword is optional and is used to specify the column names in the new table.

DROP TABLE AR_STORMWATER_pid_SAP;

CREATE TABLE AR_STORMWATER_pid_SAP 
AS (
    SELECT pid, AREARATE_CODE "ARCODE"
	FROM SAP_storm_water
	WHERE (pid, shape_area) IN
	(
		SELECT pid, MAX(shape_area)
		FROM SAP_storm_water
		GROUP BY pid
	)
);

commit;

-- Remove any records that dont have an AR code
DELETE FROM AR_STORMWATER_pid_SAP
WHERE arcode IS NULL;

commit;
--exit;



