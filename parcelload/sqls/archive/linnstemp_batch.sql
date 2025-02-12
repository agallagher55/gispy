--USE [GISRW01]
--GO

IF EXISTS(SELECT * FROM sys.tables WHERE SCHEMA_NAME(schema_id) = 'sdeadm' AND name = 'LINNS_ALL_STAGE')
   DROP TABLE [sdeadm].[LINNS_ALL_STAGE];
--GO

-- create LINNS_ALL_STAGE table
WITH
	CONDO_PID_LOOKUP AS --lookup list of Condo Unit PIDS
		(
			SELECT CAST(pid as varchar(8)) PID
			 FROM [sdeadm].[LINNS_PIDMSTRS] lpm
			 WHERE parceltype='CC'
		 ),

	MOBILE_HOME_PID_LOOKUP AS -- lookup list of Mobile Home PIDS currently from Hansen
	(
		/* replaces the custadm.parentaan_mobile_vw view */
		SELECT a.acctno, p.prclid AS pid
		FROM HANSENDATA.acctasr a
		JOIN HANSENDATA.pidgrid p ON (a.acctkey = p.acctkey)
		WHERE p.prclid IN
		(
			SELECT DISTINCT p.prclid
			FROM HANSENDATA.acctasr a
			JOIN HANSENDATA.pidgrid p ON (a.acctkey = p.acctkey)
			WHERE a.acctsubgrp = 'MOBL'
		)
		AND a.acctsubgrp = 'REG'
	),

	ASSESSMENT_LOOKUP AS  -- Lookup of Taxable Assessments from Hansen
	(
		SELECT DISTINCT ACCTNO, ASDTAXABLE
		FROM HANSENDATA.ACCTASR
	),

	FULL_LINNS_LIST AS -- full list of PIDS based on [sdeadm].[LND_parcel_polygon]
	(
		SELECT distinct
		g.pid,
		m.area,
		m.area_unit,
		n.last_name,
		n.first_name,
		n.middle_name,
		n.enterprise_name,
		n.propclass,

		CAST(t.aan as varchar(8)) aan,

		CAST(	-- sets owner_full field to Enterprise_Name if isn't not NULL otherwise to concatenated Last, First Middle names
			CASE WHEN (enterprise_name is null or enterprise_name='' or enterprise_name=' ')
				-- the use of COALESCE here eliminates the spaces and commas when some or all of the name fields are NULL
				THEN COALESCE(enterprise_name, TRIM(last_name) + COALESCE(', ' + TRIM(first_name),NULL) + COALESCE(' ' + TRIM(middle_name),NULL) )
				ELSE enterprise_name
			END as varchar(100)) as owner_full,

		RANK() OVER (PARTITION BY g.PID
			ORDER BY COALESCE(enterprise_name, TRIM(last_name) + COALESCE(', ' + TRIM(first_name),NULL) + COALESCE(' ' + TRIM(middle_name),NULL)) ASC)
			as PID_FIRSTOWNER_RANK,

		RANK() OVER (PARTITION BY g.PID
			ORDER BY COALESCE(enterprise_name,TRIM(last_name) + COALESCE(', ' + TRIM(first_name),NULL) + COALESCE(' ' + TRIM(middle_name),NULL)) DESC)
			as PID_LASTOWNER_RANK,

		CAST(LTRIM(str(m.AREA)) +
			CASE m.AREA_UNIT
				when N'A' then ' Acres'
				when N'F' then ' Square Feet'
				when N'H' then ' Hectares'
				when N'M' then ' Square Metres'
				when N'V' then ' Cubic Metres'
				else ' Unknown'
			END
			as varchar(25)) area2,

		CAST(
			CASE
 				WHEN CHARINDEX(propclass, 'PROV')>0 THEN 'PROVINCIAL'
 				WHEN CHARINDEX(propclass, 'FED')>0 THEN 'FEDERAL'
 			END as varchar(10)) type

	 FROM
		SDEADM.LND_parcel_polygon g
		LEFT OUTER JOIN SDEADM.LINNS_PIDMSTRS m ON (g.pid=m.pid)
		LEFT OUTER JOIN SDEADM.PID_owner n ON (g.pid=n.pid)
		LEFT OUTER JOIN
			(
				select PID,AAN,
				 RANK() OVER (PARTITION BY PID ORDER BY AAN DESC) as AAN_RANK
				 -- using DESC select only the last (highest) aan associated with each PID
				 -- using ASC would select only the first (lowest) aan assocaited with each PID
				 from SDEADM.LINNS_pidaantax) t ON (g.pid=t.pid and t.aan_rank=1
			 )
	 WHERE
		g.pid <> '00000000'
		AND g.pid <> ' '
	)

	SELECT
		F.PID,
		F.AAN,
		/* all the following fields excluded from LINNS_ALL_STAGE
			F.AREA,
			F.AREA_UNIT,
			F.LAST_NAME,
			F.FIRST_NAME,
			F.MIDDLE_NAME,
			F.ENTERPRISE_NAME,
			F.PROPCLASS,
			F.OWNER_FULL,
		*/
		A.ASDTAXABLE as ASSESSMENT,
		F.AREA2 AREAUNITS,

		-- OWNER1
		CASE
			WHEN (CM.PID IS NOT NULL) THEN NULL  -- sets owner1 to NULL for condos or mobile homes otherwise to first owner_full
			ELSE F.OWNER_FULL
		END as OWNER1,

		-- OWNER2
		CASE
			WHEN (CM.PID IS NOT NULL) THEN NULL  -- sets owner2 to NULL for condos or mobile homes otherwise to Last owner_full
			WHEN F.OWNER_FULL != L.OWNER_FULL THEN L.OWNER_FULL
			ELSE CAST(NULL as varchar(100))
		END as OWNER2,

		F.TYPE  -- note that TYPE is coming from the first PID record

	INTO [sdeadm].[LINNS_ALL_STAGE]  -- this line creates the new table

	FROM
		(SELECT * FROM FULL_LINNS_LIST WHERE PID_FIRSTOWNER_RANK=1) F
		JOIN
		(SELECT * FROM FULL_LINNS_LIST WHERE PID_LASTOWNER_RANK=1) L ON (F.PID=L.PID)

		LEFT OUTER JOIN
			(
				SELECT CAST(pid as varchar(8)) PID FROM CONDO_PID_LOOKUP
				UNION
				SELECT CAST(pid as varchar(8)) PID FROM MOBILE_HOME_PID_LOOKUP
			) CM ON (F.pid=CM.pid)

		LEFT OUTER JOIN
			(SELECT * FROM ASSESSMENT_LOOKUP) A ON (F.AAN=A.ACCTNO)


--SELECT *
--FROM [sdeadm].[LINNS_ALL_STAGE]
--WHERE PID IN ('41262890', '41259417', '41259466')
