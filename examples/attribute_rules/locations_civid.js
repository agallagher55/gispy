/*
    - Update related encampment sites CIV_IDs, if CIV_ID != -9999
*/

var deleted_civid_update_value = -9999;

var relatedFeatureClass = "SDEADM.LND_encampment_sites";
var relatedFeatureIDField = $feature.ENC_ID;

var relatedFeatureSet = FeatureSetByName($datastore, "GISRW01.SDEADM.LND_encampment_sites")
var updateFeatures = Filter(relatedFeatureSet, "ENC_ID = @relatedFeatureIDField")

var watchValue = $originalFeature.CIV_ID;
var newWatchValue = $feature.CIV_ID;

var updateEntryDetails = Array(0);

if (watchValue != newWatchValue) {

    // iterate over list of related features to update
    if (!IsEmpty(updateFeatures)) {

        for (var feature in updateFeatures) {

            var civ_id = $feature.CIV_ID;

            if (civ_id != deleted_civid_update_value) {
                var updateEntry = {
                    "globalID" : feature.globalID,
    
                    // Edit specified fields of related feature
                    'attributes': {
                        "CIV_ID": civ_id,
                    }
                }
                Insert(updateEntryDetails, 0, updateEntry)
            }
        }
    };

    if (!IsEmpty(updateEntryDetails)) {

        return {
    
            // Just return the field no change required
            "result": $feature.ENC_ID,  // TODO: can this field name be a variable?
        
            // 'edit' keyword indicates an edit that needs to happen. It's an array since we can make many edits.
            // **Exclude from application evaluation option must be set to true.
            
            "edit": 
                [    
                    {
                        // 'className': The name of the feature class or table to modify.
                        "className" : relatedFeatureClass,
                        "updates" : updateEntryDetails

                    },
                ],
                // "errorMessage": "Error message text"
            }
    };
};