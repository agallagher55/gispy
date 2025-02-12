import os

PARCEL_LOAD_DIR = r"C:\Workspace\Parcel_Load\Scratch"

SDE_RW = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
SDE_RO = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RO_sdeadm.sde"

# Update field list in load_linns_pidmstrs() when switching to SQL Server. 2 Spots

PARCEL_POINT_RW = os.path.join(SDE_RW, "SDEADM.LND_parcel_point")
PARCEL_POINT_SINGLE_RW = os.path.join(SDE_RW, "SDEADM.LND_parcel_point_single")
PARCEL_POINT_OLD_SDE_RW = os.path.join(SDE_RW, "SDEADM.LND_PARCEL_POINT_OLD")

LINNS_PIDMSTRS_SDE_RW = os.path.join(SDE_RW, "SDEADM.LINNS_PIDMSTRS")
LINNS_ALL_SDE_RW = os.path.join(SDE_RW, "SDEADM.LINNS_ALL")
LINNS_ALL_STAGE_RW = os.path.join(SDE_RW, "SDEADM.LINNS_ALL_STAGE")

LINNS_ALL_SDE_RO = os.path.join(SDE_RO, "SDEADM.LINNS_ALL")
LINNS_PIDMSTRS_SDE_RO = os.path.join(SDE_RO, "SDEADM.LINNS_PIDMSTRS")

LND_GHOSTED_PARCEL_LINE_RW = os.path.join(SDE_RW, "SDEADM.LND_ghosted_parcel_line")
LND_PARCEL_LINE_RW = os.path.join(SDE_RW, "SDEADM.LND_parcels", "SDEADM.LND_parcel_line")
LND_PARCEL_POLYGON_RW = os.path.join(SDE_RW, "SDEADM.LND_parcels", "SDEADM.LND_parcel_polygon")

PIDMSTRS_DBF = os.path.join(PARCEL_LOAD_DIR, "pidmstrs.dbf")
