"""
"""

import arcpy

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)


def update_event_behaviours(update_feature, event_updates: dict):
    """
    Valid update values:
        "CALIBRATE": ("STAY_PUT", "RETIRE", "MOVE"),
        "RETIRE": ("STAY_PUT", "RETIRE", "MOVE"),
        "EXTEND": ("STAY_PUT", "RETIRE", "MOVE", "COVER"),
        "REASSIGN": ("STAY_PUT", "RETIRE", "MOVE", "SNAP"),
        "REALIGN": ("STAY_PUT", "RETIRE", "MOVE", "SNAP", "COVER"),
        "REVERSE": ("STAY_PUT", "RETIRE", "MOVE"),
        "CARTO_REALIGN": ("HONOR_ROUTE_MEASURE", "HONOR_REFERENT_LOCATION")
    """

    print(f"\nUpdating Event behaviours on {update_feature}...")

    # Get updates
    calibrate_rule_update = event_updates.get("CALIBRATE", "#")
    retire_rule_update = event_updates.get("RETIRE", "#")
    extend_rule_update = event_updates.get("EXTEND", "#")
    reassign_rule_update = event_updates.get("REASSIGN", "#")
    realign_rule_update = event_updates.get("REALIGN", "#")
    reverse_rule_update = event_updates.get("REVERSE", "#")
    carto_realign_rule_update = event_updates.get("CARTO_REALIGN", "#")

    for event in event_updates:
        new_rule = event_updates[event]
        print(f"\tUpdating {event} to '{new_rule}'...")

    # arcpy.locref.ModifyEventBehaviorRules(
    #     in_feature_class=r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde\GISRW01.SDEADM.TRNLRS\GISRW01.SDEADM.E_PSAB",
    #     calibrate_rule="STAY_PUT",
    #     retire_rule="STAY_PUT",
    #     extend_rule="STAY_PUT",
    #     reassign_rule="SNAP",
    #     realign_rule="COVER",
    #     reverse_rule="STAY_PUT",
    #     carto_realign_rule="HONOR_ROUTE_MEASURE"
    # )

    arcpy.locref.ModifyEventBehaviorRules(
        in_feature_class=update_feature,
        calibrate_rule=calibrate_rule_update,
        retire_rule=retire_rule_update,
        extend_rule=extend_rule_update,
        reassign_rule=reassign_rule_update,
        realign_rule=realign_rule_update,
        reverse_rule=reverse_rule_update,
        carto_realign_rule=carto_realign_rule_update,
    )
    print(arcpy.GetMessages())


if __name__ == "__main__":

    from events import PW_EVENTS

    # Check out location referencing
    if arcpy.CheckExtension('LocationReferencing') == "Available":
        arcpy.CheckOutExtension("LocationReferencing")
        print("LocationReferencing license checked out.")

    else:
        raise ModuleNotFoundError("Unable to checkout LocationReferencing license.")

    try:
        event_updates = {
            # "CALIBRATE": "STAY_PUT",
            # "RETIRE": "STAY_PUT",
            # "EXTEND": "MOVE",
            # "REALIGN": "STAY_PUT",
            "REASSIGN": "SNAP",
            # "REVERSE": "MOVE",
            # "CARTO_REALIGN": "HONOR_ROUTE_MEASURE"
        }

        for workspace in [
            # create_fgdb(),
            r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde",
            r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde",
        ]:

            with arcpy.EnvManager(workspace=workspace):

                print(f"\nWorkspace: {workspace}")

                # for feature in PW_EVENTS:
                for feature in ["SDEADM.E_PCIJurisdicionSection500", ]:

                    feature_dataset = "SDEADM.TRNLRS"

                    print(f"Feature: {feature}")

                    update_event_behaviours(
                        update_feature=f"{feature_dataset}\{feature}",
                        event_updates=event_updates
                    )
                    print(f"\t{arcpy.GetMessages()}")

    except Exception as e:
        print(e)

    finally:
        # Check in license
        ...