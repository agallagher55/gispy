import os
import arcpy

import pandas as pd
import numpy as np

SDE = r"C:\Users\gallaga\AppData\Roaming\ESRI\ArcGISPro\Favorites\Prod_GIS_Halifax.sde"

GOV_OWN_PARCELS = os.path.join(SDE, "SDEADM.LND_PARCEL_GOVOWN_VW")
PID_NAMES = os.path.join(SDE, "SDEADM.LINNS_PIDNAMES")
GOV_PARCEL_LOOKUP = os.path.join(SDE, "LND_PARCEL_GOVOWN_LOOKUP")


def gov_corp_names() -> [list, dict]:

    # IDENTIFY ALL CORP NAMES OF PROV/FED OWNED LAND
    gov_own_parcels_fields = ["PID", "OWNER1", "OWNER2", "TYPE"]
    verified_corp_pids = [row for row in arcpy.da.SearchCursor(GOV_OWN_PARCELS, gov_own_parcels_fields)]
    verified_corp_pids_df = pd.DataFrame(verified_corp_pids, columns=gov_own_parcels_fields)
    verified_corp_pids_df.fillna("", inplace=True)

    # Filter out private owners
    private_owner_substrings = [
        "CORP", "COMPANY", "UNIVERSITY", "LIMITED", "LTD", "INCORPORATED", ",", "SCHOOL", "CLUB", "INC.", "HALL",
        "ASSOCIATION", "COOPERATIVE", "WESTERKIRK", "PRESTON AREA HOUSING FUND", "MARRIOTT", 'OWNER UNKNOWN',
        'HALIFAX REGIONAL MUNICIPALITY'
    ]
    gov_owner_substrings = ['CANADA MORTGAGE AND HOUSING CORPORATION']

    filter1_no = ~verified_corp_pids_df["OWNER1"].str.contains('|'.join(private_owner_substrings) or verified_corp_pids_df["OWNER1"] == "")
    filter1_yes = verified_corp_pids_df["OWNER1"].str.contains('|'.join(gov_owner_substrings))
    filter2_no = ~verified_corp_pids_df["OWNER2"].str.contains('|'.join(private_owner_substrings) or verified_corp_pids_df["OWNER2"] == "")
    filter2_yes = verified_corp_pids_df["OWNER2"].str.contains('|'.join(gov_owner_substrings))

    gov_owners_df = verified_corp_pids_df[(filter1_no | filter1_yes) & (filter2_yes | filter2_no)].sort_values(by="OWNER1")

    # Unique owners from both owner fields - add OWNER1, OWNER2 and get unique list
    verified_corp_names = pd.concat(
        [gov_owners_df["OWNER1"], gov_owners_df['OWNER2']]
    ).unique().tolist()

    print(f"Found {len(verified_corp_names)} unique NAMES for PROV/FED owners.")
    verified_corp_names = sorted([x for x in verified_corp_names if x])
    np.savetxt("verified_gov_corp_names.txt", np.array(verified_corp_names), delimiter="\n", fmt='%s')

    # Build owner: type map
    owner1_types = gov_owners_df[["OWNER1", "TYPE"]].drop_duplicates().rename(columns={"OWNER1": "OWNER"})
    owner2_types = gov_owners_df[["OWNER2", "TYPE"]].drop_duplicates().rename(columns={"OWNER2": "OWNER"})
    owner_types_df = pd.concat([owner1_types, owner2_types]).drop_duplicates().sort_values(by="OWNER")

    owner_groups = owner_types_df.groupby("OWNER")
    owner_sizes = owner_groups.size()

    # Remove OWNERs if categorized as more than one TYPE (PROV AND FEDERAL)
    single_categorized_corps = owner_sizes[owner_sizes < 2].index.values
    owner_types_df = owner_types_df[owner_types_df["OWNER"].isin(single_categorized_corps)]
    corp_type_map = {k: v["TYPE"] for k, v in owner_types_df.set_index("OWNER").to_dict(orient='index').items()}

    return verified_corp_names, corp_type_map


def missing_gov_pids(gov_corps) -> dict:
    """
        GET LIST OF ALL PIDS WITH A CORPNAME IN LIST OF PROV/FED CORPS
        LINNS_PIDNAMES (~323k records)
    :return - {PID: (OWNER1, OWNER2)}
    """

    pidnames_fields = ["PID", "CORPNAME"]
    pidnames_filter = "CORPNAME != ' ' AND CORPNAME IS NOT NULL"
    pidnames_data = [row for row in arcpy.da.SearchCursor(PID_NAMES, pidnames_fields, where_clause=pidnames_filter)]
    pidnames_df = pd.DataFrame(pidnames_data, columns=pidnames_fields)
    print(pidnames_df.head())

    # Only keep rows with a CORPNAME that is PROV/FED
    pidnames_df_govcorps = pidnames_df[pidnames_df['CORPNAME'].isin(gov_corps)]

    # Group data by PID
    pids_by_govcorp = pidnames_df_govcorps.groupby("PID", as_index=False)

    # Build pid: GOV Owners dictionary
    gov_pid_coorps = dict()
    for key, df in pids_by_govcorp:
        gov_pid_coorps[key] = df['CORPNAME'].tolist()

    gov_pid_coorps = {k: df['CORPNAME'].tolist() for k, df in pids_by_govcorp}

    return gov_pid_coorps


def missing_gov_parcels(pidname_gov_pids):
    """
    - Use list of Government CORPNAME PIDs and cross-reference with GOV OWN PARCEL layer to see what PIDs are missing.
    :param pidname_gov_pids:
    :return:
    """

    gov_corp_pids = [row[0] for row in arcpy.da.SearchCursor(GOV_OWN_PARCELS, "PID")]
    missing_pids = [x for x in pidname_gov_pids if x not in gov_corp_pids]
    np.savetxt("missing_gov_pids.txt", np.array(missing_pids), delimiter="\n", fmt='%s')


def prov_fed_corps(gov_own_feature):
    pass


def add_missing_pids():
    # TODO: query GOVOWN_VW to build list of PROV NAMES, FED NAMES
    pass


# Add missing PIDS


if __name__ == "__main__":
    # prov_fed_corps()
    gov_names, corp_types = gov_corp_names()
    gov_pids = missing_gov_pids(gov_names)
    missing_gov_parcels(gov_pids)

    # TODO: verify with PIDs added to lookup table
