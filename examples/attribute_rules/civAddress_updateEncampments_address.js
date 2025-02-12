/*
- Upon change in fields [FULL_CIVIC STR_NAME STR_TYPE, GSA_NAME]:
    - update civic address in related record with same CIV_ID for locations and sites feature
*/

var civid_value = $feature.CIV_ID;
var civicAddress = $feature.FULL_CIVIC + ' ' + $feature.STR_NAME + ' ' + $feature.STR_TYPE + ', ' + $feature.GSA_NAME;

// look for changes in this record's FULL_CIVIC STR_NAME STR_TYPE, GSA_NAME fields
var watchFieldDetails = {
    "FULL_CIVIC": {
        "watchValue": $originalFeature.FULL_CIVIC,
        "newWatchValue": $feature.FULL_CIVIC,
    },
    "STR_NAME": {
        "watchValue": $originalFeature.STR_NAME,
        "newWatchValue": $feature.STR_NAME,
    },
    "STR_TYPE": {
        "watchValue": $originalFeature.STR_TYPE,
        "newWatchValue": $feature.STR_TYPE,
    },
    "GSA_NAME": {
        "watchValue": $originalFeature.GSA_NAME,
        "newWatchValue": $feature.GSA_NAME,
    },
};

var siteRecordUpdates = Array(0);
var locationRecordUpdates = Array(0);

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

// Create feature set from encampment locations
var civics_featureset = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_civic_address'
);


for (var dictKey in watchFieldDetails) {

    // Identify field value to watch for status change.
    var watchValue = watchFieldDetails[dictKey]['watchValue'];  // Field names here can NOT be held in a variable like this: $originalFeature.watchField...
    var newWatchValue = watchFieldDetails[dictKey]['newWatchValue'];

    // When the watch_value field value changes, execute logic below.
    if (watchValue != newWatchValue) {

        var site_civics = Filter(encampment_sites_featureset, 'CIV_ID = @civid_value');
        var location_civics = Filter(encampment_locations_featureset, 'CIV_ID = @civid_value');
        var civic = Filter(civics_featureset, 'CIV_ID = @civid_value');

        // Update encampment sites civic information
        if (Count(site_civics) != 0) {

            // Add update record for edit dictionary - will need GlobalID
            for (var feature in site_civics) {
                
                var addEntry = {
                    // "globalID": `'${feature.globalID}'`,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
                    "globalID": feature.globalID,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
                    "attributes": {
                        "CIV_ADDRESS": civicAddress,
                    }
                };

                Insert(siteRecordUpdates, 0, addEntry)

            };
    
        };

        // Update encampment locations civic information
        if (Count(location_civics) != 0) {

            // Iterate over site_locations
            for (var feature in location_civics) {
                        
                var addEntry = {
                    // "globalID": `'${feature.globalID}'`,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
                    "globalID": feature.globalID,  // When defining global lD or global IDs keyword parameters, ensure that the value is enclosed in single quotation marks.
                    "attributes": {
                        "CIV_ADDRESS": civicAddress,
                    }
                };

                Insert(locationRecordUpdates, 0, addEntry)

            };
        };


        
    };
};


// if updateRecordDetails is not empty, return updates
if (Count(siteRecordUpdates) != 0 || Count(locationRecordUpdates)) {

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


