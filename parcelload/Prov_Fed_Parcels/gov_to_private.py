import json

from main import GovParcels, PidNames, ParcelLookup
missing_gov_own_vw_pids_json = "pidname_gov_pid_info.json"

if __name__ == "__main__":
    gov_parcels = GovParcels()
    pidname_parcels = PidNames()
    lookup_parcels = ParcelLookup()

    # What happens if a PID goes from PID owned to private?? --> Check PIDNAMES for PID LOOKUP changes to new owner
    # 1. Check PIDNAMES for PID LOOKUP changes to new owner

    # a) Get current LOOKUP table PIDs
    lookup_pids = lookup_parcels.pids

    # b) Get PIDNAME PIDs and their owners
    with open(missing_gov_own_vw_pids_json) as jfile:
        pidname_pid_info = json.load(jfile)

    # c) Ensure PIDs in LOOKUP still have PROV/FED owners - gov_owner_types.json (from GOV_OWN_PARCEL feature)
    lookup_private_pids = [pid for pid in lookup_pids if pid not in pidname_pid_info and pid not in gov_parcels.pids]
    print(f"PIDs that have changed to NOT PROV/FED: {', '.join(lookup_private_pids)}")

    # d) Remove PIDs from lookup that are no longer PROV/FED owned
    if lookup_private_pids:
        lookup_parcels.remove_pids(lookup_private_pids)

    print()

