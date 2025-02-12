var currentFeatureName = "SDEADM.LND_enampment_locations";
var relatedFeatureClass = "SDEADM.LND_encampment_sites";
var relatedFeatureIDField = $feature.ENC_ID;

var relatedFeatureSet = FeatureSetByName($datastore, "GISRW01.SDEADM.LND_encampment_sites");

var watchValue = $originalFeature.ENC_NAME;
var newWatchValue = $feature.ENC_NAME;  // IF any related outdoor rec poly is In service, set park_rec_feature as In Service


if (watchValue != newWatchValue) {

    var updateFeatures = Filter(relatedFeatureSet, "ENC_ID = @relatedFeatureIDField")

    // get the feature row of the related feature (we should only have one)  // TODO: Update this to many
    var globalidUpdateEntries = Array(0);

    for (var feature in updateFeatures) {
        
        var updateEntry = {
            "globalID" : feature.globalID,

            // Edit specified fields of related feature
            'attributes': {
                "ENC_NAME": newWatchValue,
            }
        }

        Insert(globalidUpdateEntries, 0, updateEntry)
    }
    ;
    
    return {

        // // Just return the field no change required

        // 'edit' keyword indicates an edit that needs to happen. It's an array since we can make many edits.
        // **Exclude from application evaluation option must be set to true.

        "edit": 
            [
                {
                    // 'className': The name of the feature class or table to modify.
                    "className" : relatedFeatureClass,

                    // 'adds' refers to the type of edit. In this case we want to add. It's an array since we can make many inserts
                    "updates" : globalidUpdateEntries
                }
            ],
            // "errorMessage": "Error message text"
    }
}


