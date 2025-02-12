import arcpy
import json
import os

import pandas as pd

SDE = r"C:\Users\gallaga\AppData\Roaming\ESRI\ArcGISPro\Favorites\Prod_GIS_Halifax.sde"

GOV_OWN_PARCELS = os.path.join(SDE, "SDEADM.LND_PARCEL_GOVOWN_VW")
HRM_PARCELS = os.path.join(SDE, "SDEADM.LND_hrm_parcel_parks", "SDEADM.LND_hrm_parcel")


# Get HRM parcels coded as fed/prov, not found in missing gov parcels or gov_own_vw
def hrm_prov_fed_parcels_check():
    sql = "OWNER IN ('PROV', 'FED')"

    with open("exports/missing_gov_own_vw_pids.json") as jfile:
        missing_parcels = json.load(jfile)

    view_pids = [row[0] for row in arcpy.da.SearchCursor(GOV_OWN_PARCELS, "PID")]
    missing_pids = list(missing_parcels.keys())

    hrm_prov_fed_pids = [row[0] for row in arcpy.da.SearchCursor(HRM_PARCELS, "PID", where_clause=sql)]
    hrm_questionable_prov_fed_pids = sorted([x for x in hrm_prov_fed_pids if x not in view_pids and x not in missing_pids])

    with open("hrm_parcel_fed_prov_pids.txt", "w") as txtfile:
        for row in hrm_questionable_prov_fed_pids:
            txtfile.write(f"{row}\n")

    return hrm_questionable_prov_fed_pids


def json_to_csv(json_file):
    with open(json_file) as jfile:
        data = json.load(jfile)
        print(data)

    df = pd.DataFrame.from_dict(data, orient="index", columns=["TYPE"])
    df.reset_index(inplace=True)
    df.to_csv("exports/gov_owners_and_types.csv", index=False)


if __name__ == "__main__":
    # print(hrm_prov_fed_parcels_check())

    json_to_csv("exports/gov_owners_and_types.json")
