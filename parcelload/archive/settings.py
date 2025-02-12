import os

from datetime import datetime

# TODO: UPDATE ME
PARCEL_DATA_EXTRACT_DIR = r"T:\work\giss\monthly\202403mar\gallaga\parcel_load\HRM_2024-03-05"

PARCEL_LOAD_DIR = r"C:\Workspace\Parcel_Load\Scratch"

SDE_RW = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"

PARCEL_POINT_RW = os.path.join(SDE_RW, "SDEADM.LND_parcel_point")
PARCEL_POINT_SINGLE_RW = os.path.join(SDE_RW, "SDEADM.LND_parcel_point_single")

SDEADM_LND_ghosted_parcel_line = os.path.join(SDE_RW, "SDEADM.LND_ghosted_parcel_line")
SDEADM_LND_parcel_line = os.path.join(SDE_RW, "SDEADM.LND_Parcels", "SDEADM.LND_parcel_line")
SDEADM_LND_parcel_polygon = os.path.join(SDE_RW, "SDEADM.LND_Parcels", "SDEADM.LND_parcel_polygon")

LINNS_ALL_SDE_RW = os.path.join(SDE_RW, "SDEADM.LINNS_ALL")

SDEADM_GSA_Polygon = os.path.join(SDE_RW, "SDEADM.ADM_gsa_boundaries", "SDEADM.ADM_gsa_polygon")

CURRENT_MONTH = datetime.now().strftime('%B')  # Date format YYMMDD
