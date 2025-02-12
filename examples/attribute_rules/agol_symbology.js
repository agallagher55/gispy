// iif(IsEmpty($feature.HAZARDS), 'No Hazards', 'Hazards')

// iif($feature.HAZARDS == 'No Hazards', 'No Hazards', 'Hazards')

var has_hazards = $feature.HAZARDS;

if (IsEmpty(has_hazards)) {
    return null
};

if (has_hazards == 'No Hazards') {
    return has_hazards
}
else {
    return 'Has Hazards'
}