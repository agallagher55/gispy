import os.path

import arcpy
import arcgis.features

from arcgis.gis import GIS

arcpy.env.overwriteOutput = True

# TODO: Accommodate QA vs Prod with config file
SDE_QA = r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm_branch.sde"
SDE_PROD = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm_branch.sde"

GDB = r"T:\work\giss\monthly\202407july\gallaga\LRS_partial_match_automation\lrs_automation\Default_QA.gdb"
GDB = r"T:\work\giss\monthly\202407july\gallaga\LRS_partial_match_automation\lrs_automation\Default.gdb"

LRSN_ROUTE_FEATURE = rf"{SDE_PROD}\GISRW01.SDEADM.TRNLRS\SDEADM.LRSN_Route"

PORTAL_INFO = {
    "QA": {
        "url": r"https://gisapp-int-qa.halifax.ca/portal/",
        "url_lrs_services": r"https://gisapp-int-qa.halifax.ca/extn/rest/services/LRS_EventEditor/FeatureServer",
        "username": "Halifax_Enterprise",
        "password": "Fly1ng1nTheCl0uds"
    },
    "PROD": {
        "url": r"https://gisapp-int.halifax.ca/portal/",
        "url_lrs_services": r"https://gisapp-int.halifax.ca/extn/rest/services/LRS_EventEditor/FeatureServer",
        "username": "Halifax_Enterprise",
        "password": "L00k1ng1nTheCl0uds"
    },
}

MEASURE_DELTA_THRESHOLD = 30


def compare_measures(event, prod_lrs_url, qa_lrs_url):

    # Get records updated in QA
    updated_qa_records = [
        x for x in arcpy.da.SearchCursor(
            # event,
            event.replace(prod_lrs_url, qa_lrs_url),
            ["ROUTEID", 'TOMEASURE', 'Shape__Length', 'EVENTID'],
            # "MODBY LIKE 'Halifax_Enterprise'"
            "COMMENT_ IS NOT NULL"
        )
    ]

    updated_record_count = len(updated_qa_records)
    print(f"Updated QA records {updated_record_count}")

    prod_records = {
        x[-1]: x[2] for x in arcpy.da.SearchCursor(
            event,
            ["ROUTEID", 'TOMEASURE', 'Shape__Length', 'EVENTID'],
            "MODBY LIKE 'Halifax_Enterprise'"
        )
    }

    if updated_qa_records:

        for row in updated_qa_records:

            route_id, to_measure, eventid = row[0], row[1], row[3]

            prod_to_measure = prod_records.get(route_id)

            # Compare prod TOMEASURE to lrsn route length
            lrsn_route_length = lrsn_route_lengths.get(route_id)

            if prod_to_measure != lrsn_route_length:

                percent_diff = 100 - (prod_to_measure / lrsn_route_length) * 100

                # Compare to length of
                if percent_diff > 1:
                    print(f"\tpercent diff: {percent_diff}")

                    print(
                        f"ROUTEID {route_id} has to_measure different to route length! {to_measure} vs {lrsn_route_length}. EVENTID: {eventid}")

                    print("Potential error found!")

    return updated_qa_records


if __name__ == "__main__":

    # TODO: Update Me
    environment = "QA"
    # environment = "PROD"

    service_location_errors = [
        "PARTIAL MATCH FOR THE TO-MEASURE",
    ]

    active_portal = PORTAL_INFO[environment].get("url")
    portal_user = PORTAL_INFO[environment].get("username")
    portal_pw = PORTAL_INFO[environment].get("password")

    lrs_services_url_qa = PORTAL_INFO["QA"].get("url_lrs_services")
    lrs_services_url_prod = PORTAL_INFO["PROD"].get("url_lrs_services")

    lrs_services_url = PORTAL_INFO[environment].get("url_lrs_services")

    gis = GIS(active_portal, portal_user, portal_pw)

    if gis.users.me:
        print(f"Logged into GIS: {gis.url} as {gis.users.me.username}")

    else:
        raise Exception("Failed to authenticate with the GIS portal.")

    arcpy.CheckOutExtension("LocationReferencing")

    # TODO: Get all endpoints

    service_urls = {
        # Traffic Class
        # rf"{lrs_services_url}/30",

        # Pavement projects
        # rf"{lrs_services_url}/31",

        rf"{lrs_services_url}/32",

    }

    # Get LRSN Route ID to_measures

    lrsn_route_lengths = {
        row[0]: row[1] for row in arcpy.da.SearchCursor(LRSN_ROUTE_FEATURE, ["ROUTEID", 'SHAPE.STLength()'])
    }

    print("\nProcessing Event Layers...")
    for count, service_url in enumerate(service_urls, start=1):

        print(f"Service URL: {service_url}")

        event_feature_layer = arcgis.features.FeatureLayer(service_url, gis)
        feature_layer_name = event_feature_layer.properties.name

        print(f"\n{count}/{len(service_urls)}) '{feature_layer_name}'")

        # compare_measures(service_url)

        edited_features = list()

        # event_update_field = "COMMENT_"
        event_update_field = "TOMEASURE"

        for location_error in service_location_errors:

            locerror_sql = f"LOCERROR = '{location_error}'"

            print(f"\nLOCATION ERROR SQL: {locerror_sql}")

            if location_error == 'ROUTE LOCATION NOT FOUND':

                # Export rows to feature class
                print("Exporting feature...")
                errors_fc = arcpy.ExportFeatures_conversion(
                    in_features=service_url,
                    out_features=os.path.join(GDB, f"{arcpy.ValidateTableName(feature_layer_name, GDB)}"),
                    where_clause=locerror_sql,
                )[0]
                print(arcpy.GetMessages())

                errors_count = int(arcpy.GetCount_management(errors_fc)[0])

                if errors_count > 0:

                    # Update the measure field
                    print("Updating MEASURE values in exported feature class...")
                    with arcpy.da.UpdateCursor(errors_fc, ["ROUTEID", "MEASURE", "COMMENT_"]) as uCursor:

                        for row in uCursor:
                            route_id = row[0]
                            current_measure = row[1]
                            comments = row[2]

                            update_measure = lrsn_route_lengths.get(route_id)

                            row[1] = update_measure
                            # row[2] = f"Updating measure from {current_measure} to {update_measure}"

                            print(f"Updating MEASURE from {current_measure} to {update_measure}")

                            uCursor.updateRow(row)

                    # Delete events from LRS event table
                    print("Deleting events...")
                    deleted_service_features = event_feature_layer.delete_features(
                        # deletes=None,  # A comma separated string of OIDs to remove from the service.
                        where=locerror_sql,
                        return_delete_results=True
                    )

                    # Remove editor tracking from event/Delete entries for ADDBY/ADDDATE after load

                    # Append events into LRS table
                    print(f"Appending Events ({errors_count})...")
                    arcpy.locref.AppendEvents(
                        in_dataset=errors_fc,
                        in_target_event=service_url,
                        load_type="ADD",
                        generate_event_ids="NO_GENERATE_EVENT_IDS",
                        generate_shapes="GENERATE_SHAPES"
                    )

                else:
                    print("No errors found!")

            # Get feature list
            feature_set = event_feature_layer.query(where=locerror_sql)
            feature_list = feature_set.features

            if feature_list:

                print(f"\t{len(feature_list)} features found from filter '{locerror_sql}'.")
                print(f"\nChecking if features are within {MEASURE_DELTA_THRESHOLD}m (threshold) of LRSN route length...")

                for feature in feature_list:

                    # COMPARE FEATURE TOMEASURE WITH LRSN TO_MEASURE
                    route_id = feature.get_value(field_name='ROUTEID')
                    to_measure = feature.get_value(field_name='TOMEASURE')

                    print(f"\nChecking feature with ROUTEID: '{route_id}'")

                    # Get matching TOMEASURE from LRSN_ROUTE, using ROUTEID
                    lrsn_to_measure = lrsn_route_lengths.get(route_id)
                    update_required = None

                    print(f"\tLRSN to_measure: {lrsn_to_measure}")
                    print(f"\tFeature to_measure: {to_measure}")

                    if lrsn_to_measure and to_measure:

                        # check if measures are within 30m
                        measure_diff = abs(lrsn_to_measure - to_measure)
                        update_required = measure_diff < MEASURE_DELTA_THRESHOLD
                        print(f"\tMeasure difference: {round(measure_diff, 2)}")

                    print(f"\tUpdate required: {update_required}")

                    if update_required and location_error in (
                            # "PARTIAL MATCH FOR TO-MEASURE",
                            "PARTIAL MATCH FOR THE TO-MEASURE"
                    ):

                        # # Update COMMENT_ field to track edits
                        # feature.set_value(
                        #     field_name="COMMENT_",
                        #     value=f"Updated TOMEASURE to {lrsn_to_measure} from {to_measure}"
                        # )

                        print(f"\n\tCurrent to_measure: {to_measure}")
                        print(f"\t--> LRSN to_measure: {lrsn_to_measure}")

                        # Update TOMEASURE
                        feature.set_value(
                            field_name="TOMEASURE",
                            value=lrsn_to_measure
                        )

                        print("\tFeature will be updated.")
                        edited_features.append(feature)

                if edited_features:

                    print("\nSaving edits to Feature Layer...")
                    event_feature_layer.edit_features(updates=edited_features)

                    print("\nFeature layer updated.")
                    print(f"\tUpdate counts: {len(edited_features)}")

                    # Generate events
                    try:
                        print("\nGenerating events...")
                        arcpy.CheckOutExtension("LocationReferencing")
                        arcpy.locref.GenerateEvents(in_event_layer=service_url)
                        # TODO: may have to re-run

                    except arcpy.ExecuteError:
                        print(arcpy.GetMessages())
                        print(f"Sometimes have to re-run...")

                    # finally:
                    #     arcpy.CheckInExtension('LocationReferencing')

                else:
                    print(
                        "\n\tDidn't find any features that needed editing "
                        "(features didn't meet THRESHOLD or loc error type)."
                    )

            else:
                print("**No features found (using SQL query) needing an update.")
