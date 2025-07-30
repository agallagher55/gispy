import os
import time

import arcpy

import pandas as pd

from events import LrsEventForm

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

SDE_SPATIAL_REFERENCE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde"


if __name__ == "__main__":

    # TODO: UPDATE ME
    # xl = r"T:\work\giss\monthly\202501jan\gallaga\E_PavementDistress\Pavement Distress 2024\PavementDistress_2024_New_Event_Request.xlsx"

    xls_info = {
        # r"T:\work\giss\monthly\202502feb\gallaga\E_PavementRoughness\Pavement Roughness 2016\PavementRoughness_2016_New_Event_Request.xlsx": 'E_PavementRoughness2016',
        r"T:\work\giss\monthly\202507july\gallaga\CurbCondition_2021\CurbCondition2021_New_Event_Request_250709.xlsx": {
            'sheet_name': 'DATASET DETAILS',
            'event_name': "E_CurbCondition2021"
        },
    }

    local_gdb = arcpy.CreateFileGDB_management(os.getcwd(), "scratch.gdb")[0]
    print(arcpy.GetMessages())

    if arcpy.CheckExtension('LocationReferencing') == "Available":

        arcpy.CheckOutExtension("LocationReferencing")
        print("License checked out.")

    for xl in xls_info:

        event_name = xls_info[xl]["event_name"]
        sheet_name = xls_info[xl]["sheet_name"]

        print(f"\nEvent: {event_name.upper()}")

        workbook = pd.read_excel(xl, sheet_name=None)

        lrs_form = LrsEventForm(xl, sheet_name=sheet_name)
        form_field_info = lrs_form.field_info()

        # CREATE FEATURE IN GEODATABASE
        local_lrs_feature = os.path.join(local_gdb, event_name)

        if not arcpy.Exists(local_lrs_feature):
            print(f"\nCreating event feature '{local_lrs_feature}'...")

            print(f"Creating feature class locally...")
            arcpy.CreateFeatureclass_management(
                out_path=local_gdb,
                out_name=event_name,
                geometry_type="POLYLINE",
                has_m="ENABLED",
                has_z="ENABLED",
                spatial_reference=os.path.join(SDE_SPATIAL_REFERENCE, "ADM_bylaw_area"),
            )
            print(arcpy.GetMessages())

            # TODO: Copy over domains?

            # TODO: ADD FIELDS
            current_event_fields = [x.name.upper() for x in arcpy.ListFields(local_lrs_feature)]

            print(f"\nAdding fields...")
            for info in form_field_info:

                field_type = info['Field Type'].upper()

                field_name = info[LrsEventForm.field_name_field]

                if field_name.upper() in current_event_fields or not field_name:
                    continue
                #
                # elif field_name in LrsEventForm.standard_fields:
                #     continue

                if field_name not in LrsEventForm.standard_fields:
                    print(f"\nAdding field '{field_name}'...")

                    arcpy.AddField_management(
                        local_lrs_feature,
                        field_name=field_name,
                        field_type=field_type,
                        field_precision="",
                        field_scale="",
                        field_length=info["Field Length"],
                        field_alias=info["Alias"],
                        field_is_nullable="NULLABLE",
                        field_domain=info['Domain']
                    )
                    print(arcpy.GetMessages())

                    time.sleep(1)  # Sometimes fields get processed too fast...?

                    # TODO: get field defaults and assign?
                    # arcpy.AssignDefaultToField_management(
                    #     output_event_feature,
                    #     "ROUTE_TYPE",
                    #     "HOSPITAL",
                    # )

        for sde_workspace in [
            # r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm_branch.sde",
            # r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde",
            r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde"
        ]:

            # TODO: COPY TO FEATURE DATASET
            lrs_sde_feature_dataset = os.path.join(sde_workspace, "SDEADM.TRNLRS")
            lrs_sde_routes = os.path.join(lrs_sde_feature_dataset, "SDEADM.LRSN_Route")

            sde_event_feature = os.path.join(lrs_sde_feature_dataset, f"SDEADM.{event_name}")

            print(f"\nCopying to {lrs_sde_feature_dataset}...")
            arcpy.CopyFeatures_management(
                in_features=local_lrs_feature,
                out_feature_class=sde_event_feature
            )
            print(arcpy.GetMessages())

            # ADD EDITOR TRACKING
            print("\nEnabling Editor Tracking...")
            arcpy.EnableEditorTracking_management(
                in_dataset=sde_event_feature,
                creator_field="ADDBY",
                creation_date_field="ADDDATE",
                last_editor_field="MODBY",
                last_edit_date_field="MODDATE",
                add_fields="NO_ADD_FIELDS",
                record_dates_in="UTC"
            )
            print(arcpy.GetMessages())

            # Add GlobalIDs
            print("\nAdding GlobalIDs...")
            arcpy.AddGlobalIDs_management(sde_event_feature)
            print(arcpy.GetMessages())

            # TODO: CREATE LRS EVENT FROM EXISTING DATASET
            print("\nCreating LRS event from copied dataset...")
            arcpy.locref.CreateLRSEventFromExistingDataset(
                parent_network=lrs_sde_routes,
                in_feature_class=sde_event_feature,
                event_id_field="EVENTID",
                route_id_field="ROUTEID",
                from_date_field="FROMDATE",
                to_date_field="TODATE",
                loc_error_field="LOCERROR",
                measure_field="FROMMEASURE",
                to_measure_field="TOMEASURE",
                event_spans_routes="NO_SPANS_ROUTES",
                to_route_id_field=None,
                store_route_name="NO_STORE_ROUTE_NAME",
                route_name_field=None,
                to_route_name_field=None
            )
            print(arcpy.GetMessages())

            # ADD EVENT BEHAVIOURS
            print("\nApplying event behaviours...")
            event_behaviour_ruleset = lrs_form.event_behviours()
            event_behviour_dict = {item['Activity']: item['Rule'] for item in event_behaviour_ruleset}

            arcpy.locref.ModifyEventBehaviorRules(
                in_feature_class=sde_event_feature,
                calibrate_rule=event_behviour_dict['Calibrate Route'],
                retire_rule=event_behviour_dict['Retire Route'],
                extend_rule=event_behviour_dict['Extend Route'],
                reassign_rule=event_behviour_dict['Reassign Route'],
                realign_rule=event_behviour_dict['Realign Route'],
                reverse_rule=event_behviour_dict['Reverse Route'],
                carto_realign_rule=event_behviour_dict['Carto Realign Route']
            )
            print(arcpy.GetMessages())

            # TODO: Register as branch versioned - Watch that feature doesn't get tagged as traditionally versioned by default
            print("\nMaking sure feature dataset is versioned...")
            arcpy.RegisterAsVersioned_management(lrs_sde_feature_dataset)
            print(arcpy.GetMessages())

    # arcpy.CheckInExtension("LocationReferencing")
    # print("\nLocation referencing license returned.")
