// Record each of user's OWNER values from domain. Setting to null to reset

var initialValue = $originalFeature.OWNER;
var userInput = $feature.OWNER;
var updateValue = '';

var separator = ", ";


// Will need to get domain descriptions
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
    'CSAP': 'Conseil Scolaire Acadien Provincial',
}


// make sure domain description is in domain list above
if (!HasKey(domainInfo, $feature.OWNER)) {
    return userInput
    var domainDesc = domainInfo[userInput];
    updateValue = `UPDATE VALUE NOT FOUND (Value: ${domainDesc})`
    return updateValue
} 


else {
    updateValue = domainInfo[userInput]

    // If value is Null, reset field.
    if (IsEmpty(userInput)) {
        return null
    };

    if (IsEmpty(initialValue)) {
        return updateValue;
    }

    else {

        // make sure value hasn't already been chosen.
        var currentValues = Split(initialValue, separator);

        if (Includes(currentValues, updateValue)) {
            return initialValue
        }
        else {
            return `${initialValue}${separator}${updateValue}`
        };

    };

};

