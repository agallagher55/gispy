/*
- Automatic ID assignment based on spatial intersection
*/

var target_field_name = 'ENC_ID';

// target feature needs to be written out here, can't be a variable or you will get 9999 error
var target_feature = FeatureSetByName($datastore,  'GISRW01.SDEADM.LND_encampment_locations', [target_field_name]);

var closest_features = Intersects(target_feature, Buffer($feature, 5, 'meters'));

var num_intersecting_features = Count(closest_features);

if (num_intersecting_features > 0) {
    var closest_feature_field_value = First(closest_features)[target_field_name]
    return closest_feature_field_value
};


