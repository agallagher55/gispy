ALTER TABLE ims_tab2 ADD (
type varchar2(10));

UPDATE ims_tab2
SET type = 'MUNICIPAL'
WHERE owner_code in ('53','55','56','57','99');

UPDATE ims_tab2
SET type = 'PROVINCIAL'
WHERE owner_code like 'F%';

UPDATE ims_tab2
SET type = 'FEDERAL'
WHERE owner_code like 'G%';

commit;
