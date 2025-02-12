import arcpy
import os

from gispy.replicas import replicas

if __name__ == "__main__":

    dev_rw = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde"
    dev_ro = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RO_sdeadm.sde"

    qa_rw = r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde"
    qa_ro = r"E:\HRM\Scripts\SDE\SQL\qa_RO_sdeadm.sde"

    prod_rw = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"
    prod_ro = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RO_sdeadm.sde"

    for rw_sde, ro_sde in (
            # (dev_rw, dev_ro),
            (qa_rw, qa_ro),
            (prod_rw, prod_ro),
    ):

        # replica_name = "LND_Rosde"
        # replica_name = "BLD_LND_Rosde"
        replica_name = "ADM_Rosde"
        # replica_name = "TRN_Rosde"

        replica_features = replicas.Replica(replica_name, rw_sde).datasets

        # Write current replica features
        with open(f"{replica_name}.txt", "w") as txtfile:
            for feature in sorted(list(set(replica_features))):
                txtfile.write(f"{feature}\n")

        # all_features = replica_features + new_features

        new_features = [
            "SDEADM.CEN_socio_economic_indicators",
            # "SDEADM.LND_encampment_locations",
            # "SDEADM.LND_encampment_sites",
            # "SDEADM.LND_helipad_flight_path",
            # "SDEADM.TRN_transportation_planning_proj",
            # "SDEADM.ADM_waste_coll_area",
            # "SDEADM.ADM_community_planning_program",
            # "SDEADM.ADM_traffic_analyst_zone",
            # "SDEADM.LND_ORA_STATUS_LOG",
            # "SDEADM.BLD_BUILDING",
            # "SDEADM.BLD_BUILDING_CIVIC_LINK",
            # "SDEADM.BLD_BUILDING_USE",
            # 'SDEADM.BLD_BUILDING_POLYGON'
        ]

        create_new_replica = False

        # add_features = all_features if create_new_replica else new_features

        replicas.add_to_replica(
            replica_name=replica_name,
            rw_sde=rw_sde,
            ro_sde=ro_sde,
            add_features=new_features,
            topology_dataset=False
        )

        # CHECKS
        # RW is Versioned
        # RW & RO have GlobalIDs
