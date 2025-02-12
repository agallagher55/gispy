/*
- Upon deleted record
    - If CIV_ID in locations feature:
        - update CIV_ID to -9999

    - If CIV_ID in sites feature:
        - Update record in sites —> pull intersecting CIV_ID from location OR (if not in location poly) pull nearest civic
*/

var deleted_civid_update_value = -9999;
var target_field_name = 'CIV_ID';

var SITES_CIVID_UPDATE_MSG = "*WARNING!: CIV_ID requires update. (This will be automatically fixed during next user edit with Attribute rules.)";

// Create feature set from encampment sites
var encampment_sites_featureset = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_encampment_sites'
    // ['CIV_ID', 'CIV_ADDRESS', 'GloablID']
);

// Create feature set from encampment locations
var encampment_locations_featureset = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_encampment_locations'
    // ['CIV_ID', 'CIV_ADDRESS', 'GloablID']
);

var siteRecordUpdates = Array(0);
var locationRecordUpdates = Array(0);

// Is CIV_ID in an encampment feature?
var civid_value = $feature.CIV_ID;

var site_civics = Filter(encampment_sites_featureset, 'CIV_ID = @civid_value');
var location_civics = Filter(encampment_locations_featureset, 'CIV_ID = @civid_value');


if (Count(location_civics) != 0) {

    /*
    Update record in sites —> pull intersecting CIV_ID from location OR (if not in location poly) pull nearest civic
    */
    
    // Add update record for edit dictionary - will need GlobalID.
     for (var feature in location_civics) {

        var updateEntry = {
            "globalID": feature.globalID,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
            "attributes": {
                "CIV_ID": deleted_civid_update_value,
            }
        };

        Insert(locationRecordUpdates, 0, updateEntry)

    };
};

if (Count(site_civics) != 0) {

    /*
    Update record in sites —> pull intersecting CIV_ID from location OR (if not in location poly) pull nearest civic
    */


    // GET INTERSECTING LOCATION CIV_ID
    // ...

    // GET CLOSEST CIVIC

    var civ_address_featureset = FeatureSetByName(
        $datastore,  
        'GISRW01.SDEADM.LND_civic_address'
        // [target_field_name]
    );
    
    // Add update record for edit dictionary - will need GlobalID.
    for (var site_feature in site_civics) {

        // var closest_civic_features = Intersects(
        //     civ_address_featureset, 
        //     Buffer(site_feature, 500, 'meters')
        // );

        // // Remove civic that was just deleted?
        // var closest_valid_civics = Filter(closest_civic_features, "CIV_ID <> @civid_value")

        // var min_distance = Infinity;
        // var closest_feature;
    
        // // Get closest civic
        // // for (var civic_feature in closest_civic_features) {
        // for (var civic_feature in closest_valid_civics) {

        //     // var featDistance = Distance(civic_feature, $feature, 'meters');
        //     var featDistance = Distance(civic_feature, site_feature, 'meters');
    
        //     if (featDistance < min_distance) {
        //         min_distance = featDistance;
        //         closest_feature = civic_feature;
        //     }
        // };

        // if (!IsEmpty(closest_feature)) {
            // Attribute site feature with closest civic's CIV_ID
        var updateEntry = {
            "globalID": site_feature.globalID,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
            "attributes": {
                // "CIV_ID": closest_feature.CIV_ID,
                // "CIV_ADDRESS": `${closest_feature.FULL_CIVIC} ${closest_feature['STR_NAME']} ${closest_feature['STR_TYPE']}, ${closest_feature['GSA_NAME']}`
                "NOTES": feature.NOTES + ' ' + SITES_CIVID_UPDATE_MSG,
            }
        };

        Insert(siteRecordUpdates, 0, updateEntry)
        // };

    };
};

// if updateRecordDetails is not empty, return updates
if (Count(siteRecordUpdates) != 0 || Count(locationRecordUpdates) != 0) {

    return {

        "edit": 
        [
            {
                // 'className': The name of the feature class or table to modify.
                "className" : "SDEADM.LND_encampment_locations",

                // 'adds' refers to the type of edit. In this case we want to add. It's an array since we can make many inserts
                "updates" : locationRecordUpdates
            },

            {
                // 'className': The name of the feature class or table to modify.
                "className" : "SDEADM.LND_encampment_sites",

                // 'adds' refers to the type of edit. In this case we want to add. It's an array since we can make many inserts
                "updates" : siteRecordUpdates
            },

        ],
        
        // "errorMessage": "Error message text"
    }

};


