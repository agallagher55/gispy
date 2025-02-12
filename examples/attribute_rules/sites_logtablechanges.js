var featureName = "Site";  // "Site" or "Location" are the only valid values.

var updateFeature = "SDEADM.LND_ENCAMPMENT_LOG"

var domainInfo = {
    'TNT': 'Tent',
    'MSF': 'Makeshift Structure',
    'TRL': 'Trailer',
    'MOD': 'Modular Home',
    'SCN': 'Shipping Container',
    'HUT': 'Hut/Cabin',
    'RV': 'RV',
    'CAR': 'Car',
    'NAT': 'Natural Structure',
    'UTL': 'Utility Tent',

    'UNH': 'Uninhabitable',
    'DTC': 'Deteriorated Condition',
    'STC': 'Structurally Compromised',
    'HAB': 'Habitable',
        
    'CO': 'Compliance Inspection',
    'OS': 'Outreach Staff Inspection',
    'CS': 'Clean-up Staff Inspection',
        
    'SAD': 'Sharps and associated debris',
    'DOG': 'Dogs',
    'HWS': 'Human Waste',
    'BHZ': 'Biohazards',
    'DPR': 'Drug Paraphernalia',
    'PTK': 'Propane Tank',
    'AGI': 'Aggressive Individual',
    'WPN': 'Weapon',
        
    'OCC': 'Occupied',
    'VAC': 'Vacant',
    'REP': 'Under Repair',
    'CLD': 'Closed',
    'RES': 'Reserved',
    'UNF': 'Unfit',
        
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
    "SITE_ID": {
        "watchValue": $originalFeature.SITE_ID,
        "newWatchValue": $feature.SITE_ID,
    },
    "SITE_TYPE": {
        "watchValue": $originalFeature.SITE_TYPE,
        "newWatchValue": $feature.SITE_TYPE,
    },
    "INDIV_COUNT": {
        "watchValue": $originalFeature.INDIV_COUNT,
        "newWatchValue": $feature.INDIV_COUNT,
    },
    "ENC_ID": {
        "watchValue": $originalFeature.ENC_ID,
        "newWatchValue": $feature.ENC_ID,
    },
    "ENC_NAME": {
        "watchValue": $originalFeature.ENC_NAME,
        "newWatchValue": $feature.ENC_NAME,
    },
    "CONDITION": {
        "watchValue": $originalFeature.CONDITION,
        "newWatchValue": $feature.CONDITION,
    },
    "CIV_ID": {
        "watchValue": $originalFeature.CIV_ID,
        "newWatchValue": $feature.CIV_ID,
    },
    "CIV_ADDRESS": {
        "watchValue": $originalFeature.CIV_ADDRESS,
        "newWatchValue": $feature.CIV_ADDRESS,
    },
    "PID": {
        "watchValue": $originalFeature.PID,
        "newWatchValue": $feature.PID,
    },
    "INST_DATE": {
        "watchValue": $originalFeature.INST_DATE,
        "newWatchValue": $feature.INST_DATE,
    },
    "NOTICE_DATE": {
        "watchValue": $originalFeature.NOTICE_DATE,
        "newWatchValue": $feature.NOTICE_DATE,
    },
    "REMOVE_DATE": {
        "watchValue": $originalFeature.REMOVE_DATE,
        "newWatchValue": $feature.REMOVE_DATE,
    },
    "LAST_INSP": {
        "watchValue": $originalFeature.LAST_INSP,
        "newWatchValue": $feature.LAST_INSP,
    },
    "LAST_INSP_DATE": {
        "watchValue": $originalFeature.LAST_INSP_DATE,
        "newWatchValue": $feature.LAST_INSP_DATE,
    },
    "CLEAN_DATE": {
        "watchValue": $originalFeature.CLEAN_DATE,
        "newWatchValue": $feature.CLEAN_DATE,
    },
    "HAZARDS": {
        "watchValue": $originalFeature.HAZARDS,
        "newWatchValue": $feature.HAZARDS,
    },
    "NOTES": {
        "watchValue": $originalFeature.NOTES,
        "newWatchValue": $feature.NOTES,
    },
    "STATUS": {
        "watchValue": $originalFeature.STATUS,
        "newWatchValue": $feature.STATUS,
    },
}

var addRecordDetails = Array(0);


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
                    "FEATURE_ID": $feature.ES_ID, // $feature.ASSETID,  // TODO: Can this be a variable?
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
        "result": $feature.ES_ID,  // TODO: can this field name be a variable?

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

