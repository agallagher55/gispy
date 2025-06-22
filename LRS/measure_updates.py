def update_service_tomeasures(lrsn_route_feature: str, gis_org: GIS, service_urls: list,
                              location_errors: list, measure_threshold: int, local_gdb: str):
    logger.info("Updating service tomeasures...")

    if arcpy.CheckExtension("LocationReferencing") == "Available":
        arcpy.CheckOutExtension("LocationReferencing")
        logger.info("Checked out LocationReferencing Extension")

    else:
        raise LicenseError

    # Get LRSN Route ID to_measures
    lrsn_route_lengths = {
        row[0]: row[1] for row in arcpy.da.SearchCursor(lrsn_route_feature, ["ROUTEID", 'SHAPE.STLength()'])
    }

    logger.info("Processing Event Layers...")
    for count, service_url in enumerate(service_urls, start=1):

        logger.info(f"Service URL: {service_url}")

        event_feature_layer = FeatureLayer(service_url, gis_org)
        feature_layer_name = event_feature_layer.properties.name

        logger.info(f"\n{count}/{len(service_urls)}) '{feature_layer_name}'")

        edited_features = list()

        event_tomeasure_field = "TOMEASURE"

        for location_error in location_errors:

            locerror_sql = f"LOCERROR = '{location_error}'"

            logger.info(f"LOCATION ERROR SQL: {locerror_sql}")

            if location_error == 'ROUTE LOCATION NOT FOUND':

                # Export rows to feature class
                logger.info("Exporting feature...")
                errors_fc = arcpy.ExportFeatures_conversion(
                    in_features=service_url,
                    out_features=os.path.join(local_gdb, f"{arcpy.ValidateTableName(feature_layer_name, local_gdb)}"),
                    where_clause=locerror_sql,
                )[0]
                logger.info(arcpy.GetMessages())

                errors_count = int(arcpy.GetCount_management(errors_fc)[0])

                if errors_count > 0:

                    # Update the measure field
                    logger.info("Updating MEASURE values in exported feature class...")
                    with arcpy.da.UpdateCursor(errors_fc, ["ROUTEID", "MEASURE"]) as uCursor:

                        for row in uCursor:
                            route_id = row[0]
                            current_measure = row[1]

                            update_measure = lrsn_route_lengths.get(route_id)

                            row[1] = update_measure

                            logger.info(f"Updating MEASURE from {current_measure} to {update_measure}")

                            uCursor.updateRow(row)

                    # Delete events from LRS event table
                    logger.info("Deleting events...")
                    deleted_service_features = event_feature_layer.delete_features(
                        # deletes=None,  # A comma separated string of OIDs to remove from the service.
                        where=locerror_sql,
                        return_delete_results=True
                    )

                    # TODO: Remove editor tracking from event/Delete entries for ADDBY/ADDDATE after load

                    # Append events into LRS table
                    logger.info(f"Appending Events ({errors_count})...")
                    arcpy.locref.AppendEvents(
                        in_dataset=errors_fc,
                        in_target_event=service_url,
                        load_type="ADD",
                        generate_event_ids="NO_GENERATE_EVENT_IDS",
                        generate_shapes="GENERATE_SHAPES"
                    )

                else:
                    logger.info("No errors found!")

            # Get feature list
            feature_fields = [x.get("name") for x in event_feature_layer.field_groups['fields']]

            if not "LOCERROR" in feature_fields:
                logger.info("LOCERROR field not in table...")
                continue

            feature_set = event_feature_layer.query(where=locerror_sql)
            feature_list = feature_set.features

            if feature_list:

                logger.info(f"\t{len(feature_list)} features found from filter '{locerror_sql}'.")
                logger.info(f"Checking if features are within {measure_threshold}m (threshold) of LRSN route length...")

                for feature in feature_list:

                    # COMPARE FEATURE TOMEASURE WITH LRSN TO_MEASURE
                    route_id = feature.get_value(field_name='ROUTEID')
                    to_measure = feature.get_value(field_name=event_tomeasure_field)

                    logger.info(f"Checking feature with ROUTEID: '{route_id}'")

                    # Get matching TOMEASURE from LRSN_ROUTE, using ROUTEID
                    lrsn_to_measure = lrsn_route_lengths.get(route_id)
                    update_required = None

                    logger.info(f"\tLRSN to_measure: {lrsn_to_measure}")
                    logger.info(f"\tFeature to_measure: {to_measure}")

                    if lrsn_to_measure and to_measure:
                        # check if measures are within 30m
                        measure_diff = abs(lrsn_to_measure - to_measure)
                        update_required = measure_diff < measure_threshold
                        logger.info(f"\tMeasure difference: {round(measure_diff, 2)}")

                    logger.info(f"\tUpdate required: {update_required}")

                    if update_required and location_error in (
                            # "PARTIAL MATCH FOR TO-MEASURE",
                            "PARTIAL MATCH FOR THE TO-MEASURE"
                    ):
                        logger.info(f"\tCurrent to_measure: {to_measure}")
                        logger.info(f"\t--> LRSN to_measure: {lrsn_to_measure}")

                        # Update TOMEASURE
                        feature.set_value(
                            field_name=event_tomeasure_field,
                            value=lrsn_to_measure
                        )

                        logger.info("\tFeature will be updated.")
                        edited_features.append(feature)

                if edited_features:

                    logger.info("Saving edits to Feature Layer...")
                    event_feature_layer.edit_features(updates=edited_features)

                    logger.info("\nFeature layer updated.")
                    logger.info(f"\tUpdate counts: {len(edited_features)}")

                    # Generate events
                    try:
                        logger.info("\nGenerating events...")
                        arcpy.CheckOutExtension("LocationReferencing")
                        arcpy.locref.GenerateEvents(in_event_layer=service_url)
                        # TODO: may have to re-run

                    except arcpy.ExecuteError:
                        logger.info(arcpy.GetMessages())
                        logger.info(f"Sometimes have to re-run...")

                    finally:
                        arcpy.CheckInExtension('LocationReferencing')

                else:
                    logger.info(
                        "\n\tDidn't find any features that needed editing "
                        "(features didn't meet THRESHOLD or loc error type)."
                    )

            else:
                logger.info("**No features found (using SQL query) needing an update.")

if __name__ == "__main__":
    
    portal_user = config.get("Portal_Admin", "username")
    portal_pw = config.get("Portal_Admin", "password")
    portal_url = config.get("Portal_Admin", "url")
    
    gis = GIS(portal_url, portal_user, portal_pw)

    if gis.users.me:
        logger.info(f"Logged into GIS: {gis.url} as {gis.users.me.username}")

    lrs_services_url = f"{portal_url.replace('portal', 'extn/rest/services/LRS_EventEditor/FeatureServer')}"

    lrs_service_urls = [
        f"{lrs_services_url}/{i}" for i in range(43)
        # UPDATE THIS BASED ON NUMBER OF LAYERS IN THE SERVICE - range(#) goes up to, but doesnt include '#'
    ]

    service_location_errors = [
        "PARTIAL MATCH FOR THE TO-MEASURE",
    ]

    lrsn_route_feature = os.path.join(SDEADM_RW, "GISRW01.SDEADM.TRNLRS", "SDEADM.LRSN_Route")

    # Update Measures in LRS service
    update_service_tomeasures(
        lrsn_route_feature=lrsn_route_feature,
        gis_org=gis,
        service_urls=lrs_service_urls,
        location_errors=service_location_errors,
        measure_threshold=30,
        local_gdb=scratchGdb
    )
