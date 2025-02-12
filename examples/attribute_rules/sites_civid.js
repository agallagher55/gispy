/*
IF in encampment, pull this information from LND_encampment_locations(?)
IF NOT, populate with closest civic address point
*/

var target_field_name = 'CIV_ID';
var deleted_civid_update_value = -9999;


// Does intersecting LND_encampment_location have a CIV_ID?
var target_feature = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_encampment_locations', // target feature needs to be written out here, can't be a variable or you will get 9999 error
    [target_field_name]
);  

var closest_features = Intersects(target_feature, Buffer($feature, 2, 'meters'));

var num_intersecting_features = Count(closest_features);

if (num_intersecting_features > 0) {

    var closest_feature_field_value = First(closest_features)[target_field_name]

    if (!IsEmpty(closest_feature_field_value) && (closest_feature_field_value != deleted_civid_update_value)) {
        return closest_feature_field_value
    }
};



// If intersecting LND_encampment_location does NOT have a CIV_ID OR CIV_ID is invalid, get closest civ_id
var civ_address_feature = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_civic_address', 
    [target_field_name]
);

var closest_civ_features = Intersects(
    civ_address_feature, 
    Buffer($feature, 500, 'meters')
);

var min_distance = Infinity;
var closest_feature;

for (var feat in closest_civ_features) {
    var featDistance = Distance(feat, $feature, 'meters');

    if (featDistance < min_distance) {
        min_distance = featDistance;
        closest_feature = feat;
    }
};

iif(
    closest_feature != null, 
    closest_feature[target_field_name], 
    null
);
