/*
- attribute rule for automatic civic address (concatenated) population based on CIVIC_ID
*/

var civid_value = $feature['CIV_ID'];

// Create feature set from civics
var civics_featureset = FeatureSetByName(
    $datastore,  
    'GISRW01.SDEADM.LND_civic_address', 
    ['FULL_CIVIC', 'STR_NAME', 'STR_TYPE', 'GSA_NAME']
);


if (!IsEmpty($feature['CIV_ID'])) {

    var filtered_civics = Filter(civics_featureset, `CIV_ID = ${civid_value}`);

    if (Count(filtered_civics) == 0) {
        return 'ADDRESS NOT FOUND.'
    }

    else {
        // Get civic information from civic address
        var civic_record = First(filtered_civics);

        return `${civic_record['FULL_CIVIC']} ${civic_record['STR_NAME']} ${civic_record['STR_TYPE']}, ${civic_record['GSA_NAME']}`
    }

}

else {
    return null;
}
;

