"""
May 30, 2022
Approx. run time: 0.40s

Script Variables: SDE Path
Files Created: gov_owner_type.json, missing_gov_own_parcel_info.json, pidname_gov_info.json
https://docs.google.com/drawings/d/1tXfYvKMlHLJhyuD8a136YlfI8i3H8XzMxpx60ZLCK88/edit
"""

import os
import arcpy
import json
import csv
import functools

import pandas as pd

from datetime import datetime

import logger

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

TODAY = datetime.today().date().strftime('%m%d%Y')
LOG_FILE = "logs/logs_{}.log".format(TODAY)

my_logger = logger.setupLog(LOG_FILE)

DEV_SDE = r"C:\Users\gallaga\AppData\Roaming\ESRI\ArcGISPro\Favorites\DEV_RW_sdeadm.sde"
QA_SDE = r"C:\Users\gallaga\AppData\Roaming\ESRI\ArcGISPro\Favorites\QA_RW_sdeadm.sde"
PROD_SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"

SDE = PROD_SDE

GOV_OWN_PARCELS = os.path.join(SDE, "SDEADM.LND_PARCEL_GOVOWN_VW")
PID_NAMES = os.path.join(SDE, "SDEADM.LINNS_PIDNAMES")
GOV_PARCEL_LOOKUP = os.path.join(SDE, "SDEADM.LND_PARCEL_GOVOWN_LOOKUP")

# TODO: Add config file


def enable_sde_edits(function):

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        edit = arcpy.da.Editor(SDE)
        edit.startEditing(True, True)
        edit.startOperation()

        result = function(*args, **kwargs)

        edit.startOperation()
        edit.stopEditing(True)

        arcpy.ClearWorkspaceCache_management()
        del edit

        return result
    return wrapper


class GovParcels:
    """"""

    def __init__(self):
        self.source = GOV_OWN_PARCELS
        self.fields = ["PID", "OWNER1", "OWNER2", "TYPE"]

        self.df = pd.DataFrame(
            [row for row in arcpy.da.SearchCursor(self.source, self.fields)], columns=self.fields
        ).fillna("")
        self.pids = self.df['PID'].unique().tolist()

        self.owner_type_info = None
        self.private_owner_pids = list()

    def __str__(self):
        return f"{self.source}"

    def owner_info(self) -> dict:
        """
        - There are private owner names in GOV OWN VW - need to filter these out to get list of GOV OWNERS.
            Double check these PIDs with POL to see verified owner. Can take out private owners if private PIDs?

        - Build list of verified gov owners
        - Include PROV/FED owner type (will need this for lookup table

        - Include keywords in private_or_municipal_owners to exclude from master PROV/FED reference list
        :return: {owner: type,…}
        """

        from owners import (
            FED_OWNERS,
            PROV_OWNERS,
            NON_PROV_FED_OWNERS
        )

        print(f"Building Owner-PROV/FED list...")

        # Filter for gov owners
        prov_fed_owners = PROV_OWNERS + FED_OWNERS

        gov_owners_1 = self.df["OWNER1"].str.contains('|'.join(prov_fed_owners))
        gov_owners_2 = self.df["OWNER2"].str.contains('|'.join(prov_fed_owners))

        # Filter out private owners
        private_owners_1 = self.df["OWNER1"].str.contains('|'.join(NON_PROV_FED_OWNERS) or self.df["OWNER1"] == "")
        private_owners_2 = self.df["OWNER2"].str.contains('|'.join(NON_PROV_FED_OWNERS))

        # Get private owners
        private_owners = self.df[(private_owners_1 & ~gov_owners_1) | (private_owners_2 & ~gov_owners_2)].sort_values(by="OWNER1")
        private_owners.to_csv("exports/private_owners_in_parcelgovownvw.csv", index=False)
        self.private_owner_pids = sorted(private_owners["PID"].unique().tolist())

        # DataFrame with only GOV Owners
        gov_owners_df = self.df[
            (~private_owners_1 | gov_owners_1) & (gov_owners_2 | ~private_owners_2)
        ].sort_values(by="OWNER1")

        # Build owner: type map
        owner1_types = gov_owners_df[["OWNER1", "TYPE"]].drop_duplicates().rename(columns={"OWNER1": "OWNER"})
        owner2_types = gov_owners_df[["OWNER2", "TYPE"]].drop_duplicates().rename(columns={"OWNER2": "OWNER"}).sort_values(by="OWNER")
        owner_types_df = pd.concat([owner1_types, owner2_types]).drop_duplicates().sort_values(by="OWNER")

        # Remove OWNERs if categorized as more than one TYPE (PROV AND FEDERAL) - can't determine if prov or fed
        owner_groups = owner_types_df.groupby("OWNER")
        owner_group_sizes = owner_groups.size()

        multi_classified_owners = owner_group_sizes[owner_group_sizes > 1].index.values.tolist()

        # Review these owners (categorized as both provincial and federal at times)
        if multi_classified_owners:
            with open("exports/multi_classified_owners.csv", "w", newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["OWNER"])
                for owner in sorted(list({x for x in multi_classified_owners})):
                    writer.writerow([owner])

        single_categorized_corps = owner_group_sizes[owner_group_sizes < 2].index.values
        owner_types_df = owner_types_df[owner_types_df["OWNER"].isin(single_categorized_corps)]

        corp_type_map = {k: v["TYPE"] for k, v in owner_types_df.set_index("OWNER").to_dict(orient='index').items()}

        # Add in any missing explicitly defined prov/fed owners
        for owner in FED_OWNERS:
            corp_type_map[owner] = "FEDERAL"

        for owner in PROV_OWNERS:
            corp_type_map[owner] = "PROVINCIAL"

        self.owner_type_info = corp_type_map
        return corp_type_map

    def get_missing_pids(self, pidname_pid_owners: dict):
        """
        Use list of Government CORPNAME PIDs and cross-reference with GOV OWN PARCEL layer to see what PIDs are missing.
        :param pidname_pid_owners: list of PROV/FED pids, with it's owner(s) to
        :return: {PID: {"OWNER1": owner1, "OWNER2": owner2, "TYPE": type},...}
        """

        print("Checking current GOV PARCEL feature for PIDs...")
        # Flag the gov PIDs from PIDNAMES that are not in LND_PARCEL_GOVOWN_VW
        missing_pids = [pid for pid in pidname_pid_owners if pid not in self.pids]

        if missing_pids:

            # Need access to Owner Info dictionary to assign owner to pidname pid - PIDNAME table only has OWNER
            if not self.owner_type_info:
                self.owner_info()  # {owner: type,…}

            # Check owner in gov_owner_type.json
            missing_pids_types = dict()

            for pid in missing_pids:

                # Get owners associated with PID
                owners = pidname_pid_owners[pid]
                owner1 = owners[0]
                owner2 = owners[1] if len(owners) > 1 else ""

                # Get PROVINCIAL/FEDERAL from LND_PARCEL_GOVOWN_VW mapping
                # Check owner 1 and then owner 2, if owner 1 is null
                owner_type = self.owner_type_info.get(owner1, "") or self.owner_type_info.get(owner2, "")

                missing_pids_types[pid] = {
                    "OWNER1": owner1,
                    "OWNER2": owner2,
                    "TYPE": owner_type
                }

            return missing_pids_types


class PidNames:
    """"""

    def __init__(self):
        self.source = PID_NAMES
        self.fields = ["PID", "CORPNAME"]
        self.filter = "CORPNAME != ' ' AND CORPNAME IS NOT NULL"

        self.df = pd.DataFrame(
            [row for row in arcpy.da.SearchCursor(self.source, self.fields, where_clause=self.filter)], columns=self.fields
        ).fillna("")
        self.pids = self.df['PID'].unique().tolist()

    def __str__(self):
        return f"{self.source}"

    def pids_with_owners(self, pid_owners: list) -> dict:
        """
        - Build list of pids with owners from owners list parameter
        :param pid_owners:
        :return: {pid: owner,...}
        """

        print(f"Building list of Gov (PROV/FED) PID-Owners from PIDNAMES feature...")

        # Only keep rows with a CORPNAME that is PROV/FED
        df_pids = self.df[self.df['CORPNAME'].isin(pid_owners)]

        # Group data by PID
        df_by_pid = df_pids.groupby("PID", as_index=False)

        # Build PID: GOV Owners dictionary
        pid_names = dict()
        for pid, df in df_by_pid:
            owners = df['CORPNAME'].unique().tolist()
            pid_names[pid] = owners

        return pid_names


class ParcelLookup:
    def __init__(self):
        self.source = GOV_PARCEL_LOOKUP
        self.fields = ["PID", "OWNER1", "OWNER2", "TYPE"]

        self.df = pd.DataFrame(
            [row for row in arcpy.da.SearchCursor(self.source, self.fields)], columns=self.fields
        ).fillna("")
        self.pids = self.df['PID'].unique().tolist()

    def __str__(self):
        return f"{self.source}"

    def owner_info(self):
        # Get all provincial records
        prov_names_df = self.df[self.df["TYPE"] == "PROVINCIAL"]
        fed_names_df = self.df[self.df["TYPE"] == "FEDERAL"]

        # Record owners
        prov_names = pd.concat([prov_names_df["OWNER1"], prov_names_df["OWNER2"]]).unique().tolist()
        fed_names = pd.concat([fed_names_df["OWNER1"], fed_names_df["OWNER2"]]).unique().tolist()

        owner_types = {k: "PROVINCIAL" for k in prov_names if k != ""}
        owner_types.update({k: "FEDERAL" for k in fed_names if k != ""})

        return owner_types

    @enable_sde_edits
    def update_lookup(self, new_pid_info: dict, delete_pid_info: dict):
        """
        Add PIDs to LOOKUP feature
        :param new_pid_info:
        :return:
        """

        filtered_new_pid_info = {k: v for k, v in new_pid_info.items() if k not in self.pids}
        num_pids_to_be_added = len(filtered_new_pid_info)

        print(f"\n{num_pids_to_be_added} PIDs to be added to LOOKUP table...")
        my_logger.info(f"{num_pids_to_be_added} PIDs to be added to LOOKUP table...")
        my_logger.info(', '.join(filtered_new_pid_info))

        if num_pids_to_be_added > 0:

            safe_to_continue = input(f"Press the 'N' key to abort with editing SDE feature '{GOV_PARCEL_LOOKUP}'")

            if safe_to_continue.upper() == "N":
                return

            print("Updating PARCEL LOOKUP feature...")
            cursor = arcpy.da.InsertCursor(self.source, self.fields)

            for pid in filtered_new_pid_info:
                type = filtered_new_pid_info[pid].get("TYPE", "")
                owner1 = filtered_new_pid_info[pid].get("OWNER1", "")
                owner2 = filtered_new_pid_info[pid].get("OWNER2", "")

                cursor.insertRow((pid, owner1, owner2, type))
                print(f"{pid}: {type} - {owner1}, {owner1}")
                print("\trow inserted")

            # TODO: Add private owner PIDs to lookup table
            for record in delete_pid_info:
                pid = record.get("PID", "")
                type = "PRIVATE"
                owner1 = record.get("OWNER1", "")
                owner2 = record.get("OWNER2", "")
                cursor.insertRow((pid, owner1, owner2, type))

            del cursor

            # TODO: Add check for current LOOKUP PIDs that were private that may now have new, PROV/FED owners
            # TODO: Update view definition to :
            """
                SELECT p.OBJECTID, p.SHAPE, p.PID, p.FCODE, a.TYPE, a.OWNER1, a.OWNER2
                FROM (
                    SELECT PID, TYPE, OWNER1, OWNER2
                    FROM SDEADM.LINNS_ALL
                    UNION ALL
                    SELECT PID, TYPE, OWNER1, OWNER2
                    FROM SDEADM.LND_PARCEL_GOVOWN_LOOKUP
                ) a
                JOIN SDEADM.LND_PARCEL_POLYGON p ON p.PID = a.PID
                WHERE a.TYPE IN ('PROVINCIAL', 'FEDERAL') 
                    AND a.TYPE NOT LIKE 'PRIVATE'
            """

            return filtered_new_pid_info

    @enable_sde_edits
    def remove_pids(self, pids):
        """
        Remove PIDs already in LOOKUP feature
        :param pids:
        :return:
        """

        num_pids_to_be_removed = len(pids)
        print(f"\n{num_pids_to_be_removed} PIDs to be removed to LOOKUP table...")
        my_logger.info(f"{num_pids_to_be_removed} PIDs to be removed to LOOKUP table...")

        if num_pids_to_be_removed > 0:

            safe_to_continue = input(f"Press the 'N' key to abort with editing SDE feature '{self.source}'")

            if safe_to_continue.upper() == "N":
                return

            print("Removing records from PARCEL LOOKUP feature...")
            with arcpy.da.UpdateCursor(self.source, self.fields) as cursor:
                lookup_pid_index = cursor.fields.index("PID")

                for row in cursor:
                    lookup_pid = row[lookup_pid_index]

                    if lookup_pid in pids:
                        cursor.deleteRow()
                        row_info = ' | '.join([x for x in row if x])

                        print(f"\t{row_info}")
                        print("\t\tRow Deleted.")
                        my_logger.info(f"Row Deleted: {', '.join([x for x in row if x])}")

            return pids


if __name__ == "__main__":

    gov_own_vw_parcels = GovParcels()
    pidname_parcels = PidNames()
    lookup_parcels = ParcelLookup()

    # 1) Build dictionary of Gov Owners and Type (PROV/FED)
    lookup_owner_types = lookup_parcels.owner_info()  # {owner: type,…}
    gov_owner_types = gov_own_vw_parcels.owner_info()  # {owner: type,…}
    gov_owner_types.update(lookup_owner_types)

    with open("exports/gov_owners_and_types.json", "w") as jfile:
        sorted_owner_types = {k: v for k, v in sorted(gov_owner_types.items(), key=lambda x: x[0])}
        json.dump(sorted_owner_types, jfile, indent=4)

    # 2) Get PIDs in PIDNAMES with GOV Owner names
    gov_owner_names = list(gov_owner_types.keys())

    pidname_gov_pids = pidname_parcels.pids_with_owners(gov_owner_names)  # {PID: owner,...}

    print(f"\nPIDNAME prov/fed-owned pids: {len(pidname_gov_pids)}")
    my_logger.info(f"PIDNAME prov/fed-owned pids: {len(pidname_gov_pids)}")

    with open("exports/pidname_gov_pids.json", "w") as jfile:
        json.dump(pidname_gov_pids, jfile, indent=4)

    # 3) Check GOV OWN VW table for PIDs that were in PIDNAMES but not in LND_PARCEL_GOVOWN_VW
    missing_gov_own_vw_pids = gov_own_vw_parcels.get_missing_pids(pidname_gov_pids)  # {PID: [owner#, owner#, ], }

    if missing_gov_own_vw_pids:
        print(f"\nMissing gov-owned pids: {len(missing_gov_own_vw_pids)}")
        my_logger.info(f"Missing gov-owned pids: {len(missing_gov_own_vw_pids)}")

        with open("exports/missing_gov_own_vw_pids.json", "w") as jfile:
            json.dump(missing_gov_own_vw_pids, jfile, indent=4)

        with open("exports/missing_gov_own_vw_pids.csv", "w", newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["PID"])
            for pid in missing_gov_own_vw_pids:
                writer.writerow([pid])

    # Update LND_PARCEL_GOVOWN_LOOKUP table with GOV Owner PIDs not already in GOV OWN VW
    remove_pids_df = gov_own_vw_parcels.df[gov_own_vw_parcels.df["PID"].isin(gov_own_vw_parcels.private_owner_pids)]
    remove_pids_info = remove_pids_df.set_index("PID").to_dict(orient='records')
    lookup_parcels.update_lookup(missing_gov_own_vw_pids, remove_pids_info)

    # ================= ERROR CHECKING =================

    # TODO: Add check for current LOOKUP PIDs that may now have new, non-PROV/FED owners
    # TODO: Add check for current LOOKUP PIDs that were private that may now have new, PROV/FED owners

    # Make sure PIDs in LOOKUP_VW are still Prov/Fed owned.
    # a) Get current LOOKUP table PIDs
    lookup_pids = lookup_parcels.pids

    # b) Ensure PIDs in LOOKUP still have PROV/FED owners
    lookup_pids_now_private = [pid for pid in lookup_pids if pid not in pidname_gov_pids]
    if lookup_pids_now_private:
        print(f"\nPIDs in lookup table that are not prov/fed-owned: {', '.join(lookup_pids_now_private)}")
        my_logger.info(f"PIDs in lookup table that are not prov/fed-owned: {', '.join(lookup_pids_now_private)}")

        # Remove PIDs from lookup that are no longer PROV/FED owned
        lookup_parcels.remove_pids(lookup_pids_now_private)

    # TODO: remove private owners from current view layer
    # TODO: Add to the end of monthly parcel load process
    # TODO: Add disclaimer about Government Property – Federal and Government Property – Provincial, layers in the
    #  Property App
