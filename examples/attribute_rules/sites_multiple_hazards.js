// Record each of user's OWNER values from domain. Setting to null to reset

var initialValue = $originalFeature.HAZARDS;
var userInput = $feature.HAZARDS;
var updateValue = '';

var separator = ", ";


// Will need to get domain descriptions
var domainInfo = {
    'AGI': 'Agressive Individual',
    'BHZ': 'Biohazards',
    'DOG': 'Dogs',
    'DPR': 'Drug Paraphernalia',
    'HWS': 'Human Waste',
    'PTK': 'Halifax Propane Tank',
    'SAD': 'Sharps and associated debris',
    'WPN': 'Weapon',
    'NH': 'No Hazards'
}


// make sure domain description is in domain list above
if (!HasKey(domainInfo, $feature.HAZARDS)) {
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

    if (updateValue == 'No Hazards') {
        return updateValue;
    }

    if (IsEmpty(initialValue) || initialValue == 'No Hazards') {
        return updateValue;
    }

    else {

        // Make sure value hasn't already been chosen.
        var currentValues = Split(initialValue, separator);
        
        // If the hazard is already in the list of hazards, no update required.
        if (Includes(currentValues, updateValue)) {
            return initialValue
        }
        else {
            return `${initialValue}${separator}${updateValue}`
        };

    };

};

