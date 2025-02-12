// LND_encampment_locations
var featureName = "Location";  // "Site" or "Location" are the only valid values.

// Record LND_outdoor_rec_poly ASSETSTAT changes. Log ASSETID, ASSETSTAT, MODDDATE, MODBY of LND_outdoor_rec_poly in LND_ora_status_log
// https://pro.arcgis.com/en/pro-app/3.0/help/data/geodatabases/overview/attribute-rule-dictionary-keywords.htm
var updateFeature = "SDEADM.LND_ENCAMPMENT_LOG"

var domainInfo = {
    'HW': 'Halifax Water',
    'UN': 'Unknown',
    'HRSB': 'Halifax Regional School Board',
    'HRM': 'Halifax Regional Municipality',
    'PRIV': 'Private',
    'DND': 'Department of National Defence',
    'FED': 'Federal',
    'HIAA': 'Halifax International Airport Authority',
    'NA': 'Not Applicable',
    'PROV': 'Provincial',
    'CNDO': 'Condominium',
    'CSAP': 'Conseil scolaire acadien provincial',
        
    'ACT': 'Active',
    'INA': 'Inactive',
    'PEN': 'Pending',
    'TRN': 'Transitioning',
    'ATR': 'At Risk',
    'REA': 'Reactivated',
        
    'AC': 'Computer Assisted Drafting',
    'CG': 'Cogo',
    'DG': 'Digitize',
    'DV': 'Derived',
    'GP': 'Global Position',
    'IN': 'Interactive',
    'PH': 'Photogrammetric',
    'SI': 'Scanned Image',
    'TS': 'Total Station',
    'XY': 'Coordinated Point',
}

// Iterate over watch fields
var watchFieldDetails = {
    "ENC_NAME": {
        "watchValue": $originalFeature.ENC_NAME,
        "newWatchValue": $feature.ENC_NAME,
    },
    "ENC_TYPE": {
        "watchValue": $originalFeature.ENC_TYPE,
        "newWatchValue": $feature.ENC_TYPE,
    },
    "ENC_SIZE_MAX": {
        "watchValue": $originalFeature.ENC_SIZE_MAX,
        "newWatchValue": $feature.ENC_SIZE_MAX
    },
    "CIV_ID": {
        "watchValue": $originalFeature.CIV_ID,
        "newWatchValue": $feature.CIV_ID
    },
    "CIV_ADDRESS": {
        "watchValue": $originalFeature.CIV_ADDRESS,
        "newWatchValue": $feature.CIV_ADDRESS
    },
    "SERVICES": {
        "watchValue": $originalFeature.SERVICES,
        "newWatchValue": $feature.SERVICES
    },
    "FACILITIES": {
        "watchValue": $originalFeature.FACILITIES,
        "newWatchValue": $feature.FACILITIES
    },
    "OWNER": {
        "watchValue": $originalFeature.OWNER,
        "newWatchValue": $feature.OWNER
    },
    "NOTES": {
        "watchValue": $originalFeature.NOTES,
        "newWatchValue": $feature.NOTES
    },
    "STATUS": {
        "watchValue": $originalFeature.STATUS,
        "newWatchValue": $feature.STATUS
    },
    "DATE_EST": {
        "watchValue": $originalFeature.DATE_EST,
        "newWatchValue": $feature.DATE_EST
    },
    "DATE_DISB": {
        "watchValue": $originalFeature.DATE_DISB,
        "newWatchValue": $feature.DATE_DISB
    }
}

var addRecordDetails = Array();

// Record geometry change, ignoring newly created features.
if (!IsEmpty($originalFeature.ENC_ID)) {

    if ($originalFeature['Shape.STArea()'] != $feature['Shape.STArea()'])  {

        var addEntry = {
            "attributes":
                {
                    "FEATURE_ID": $feature.ENC_ID,
                    "FEATURE_TYPE": featureName,
                    "FIELD_NAME": "SHAPE",
                    "OLD_VALUE": "Old Geometry",
                    "NEW_VALUE": "New Geometry",
                    "COMMENTS": "Check archiving for specific change details."
                },
        }
        
        Insert(addRecordDetails, 0, addEntry)
    };

};


for (var dictKey in watchFieldDetails) {

    var watchField = dictKey;

    // Identify field value to watch for status change.
    var watchValue = watchFieldDetails[dictKey]['watchValue'];  // Field names here can NOT be held in a variable like this: $originalFeature.watchField...
    var newWatchValue = watchFieldDetails[dictKey]['newWatchValue'];

    // TODO: build out addRecordDetails Array to track what records need to be added to the log table.

    // When the watch_value field value changes, execute logic below.
    if (watchValue != newWatchValue) {

        if (HasKey(domainInfo, newWatchValue)) {
            newWatchValue = domainInfo[newWatchValue]
        }

        if (HasKey(domainInfo, watchValue)) {
            watchValue = domainInfo[watchValue]
        }

        var addEntry = {
            "attributes":
                {
                    "FEATURE_ID": $feature.ENC_ID, // $feature.ASSETID,  // TODO: Can this be a variable?
                    "FEATURE_TYPE": featureName, // newWatchValue,  //watchValue,  // This will log OLD VALUE, not old value. TODO: Confirm this is what's wanted
                    "FIELD_NAME": watchField,  // This is translating to a '0' value... regardless if watch value is null first or not
                    "OLD_VALUE": watchValue,
                    "NEW_VALUE": newWatchValue,
                },
        }

        Insert(addRecordDetails, 0, addEntry)
    }
}

if (!IsEmpty(addRecordDetails)) {
    
    return {

        // Just return the field no change required
        "result": $feature.ENC_ID,  // TODO: can this field name be a variable?

        // 'edit' keyword indicates an edit that needs to happen. It's an array since we can make many edits.
        // **Exclude from application evaluation option must be set to true.

        "edit": [
            {
                // 'className': The name of the feature class or table to modify.
                "className" : updateFeature,

                // 'adds' refers to the type of edit. In this case we want to add. It's an array since we can make many inserts
                "adds" : addRecordDetails
                }
            ],
            // "errorMessage": "Error message text"
    }

}


