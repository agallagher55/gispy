// set on ID field of sites, locations
// Update fields

// Record LND_outdoor_rec_poly ASSETSTAT changes. Log ASSETID, ASSETSTAT, MODDDATE, MODBY of LND_outdoor_rec_poly in LND_ora_status_log
// https://pro.arcgis.com/en/pro-app/3.0/help/data/geodatabases/overview/attribute-rule-dictionary-keywords.htm
var updateFeature = "SDEADM.LND_ORA_status_log"

// Identify field value to watch for status change.
// Use the $originalfeature global variable to reference a feature's attributes before an edit is made.
// Compare $originalfeature and $feature through Arcade to determine whether a feature's attribute has changed.
var watchValue = $originalFeature.ASSETSTAT;
var newWatchValue = $feature.ASSETSTAT;

// When the watch_value field value changes, execute logic below.
if (watchValue != newWatchValue) {
    return {
       // Just return the field no change required
      "result": $feature.ASSETID,
       // 'edit' keyword indicates an edit that needs to happen. It's an array since we can make many edits.
       // **Exclude from application evaluation option must be set to true.
       "edit": [
           {
               // 'className': The name of the feature class or table to modify.
               "className" : updateFeature,
                // 'adds' refers to the type of edit. In this case we want to add. It's an array since we can make many inserts
               "adds" : [
                            {
                                // Edit specified fields.
                                "attributes":
                                    {
                                        "ASSETID": $feature.ASSETID,
                                        "ASSETSTAT": newWatchValue,  //watchValue,  // This will log OLD VALUE, not old value. TODO: Confirm this is what's wanted
                                        "MODDATE": ToLocal(now()),  // "MODDATE": $feature.MODDATE,
                                        "MODBY": $feature.MODBY,
                                    },
                            },
                        ]
            }
        ],
        // "errorMessage": "Error message text"
    }
}