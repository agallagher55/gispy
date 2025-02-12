var target_feature_name = 'SDEADM.LND_hrm_parcel';
var target_field_name = 'ASSET_ID';
var search_distance = 200;

var target_feature = FeatureSetByName($datastore, 'GISRW01.SDEADM.LND_hrm_parcel', [target_field_name]);
var closest_features = Intersects(target_feature, Buffer($feature, 200, 'meters'));

var min_distance = Infinity;
var closest_feature;

for (var feat in closest_features) {
var featDistance = Distance(feat, $feature, 'meters');

if (featDistance < min_distance) {
min_distance = featDistance;
closest_feature = feat;
}
};

iif(closest_feature != null, closest_feature[target_field_name], null);
