/*
- attribute rule for automatic civic address (concatenated) calculation based on CIVIC_ID
*/

// SHOULD REFERENCE OWN FEATURE'S CIV_ID because SITE.CIV_ID has all additional logic 

var featureCivID = $feature.CIV_ID;

if (!IsEmpty(featureCivID)) {

    // Get address from nearest civic, returning 'ADDRESS NOT FOUND' if closest civ_id is invalid
    var civics_featureset = FeatureSetByName($datastore,  'GISRW01.SDEADM.LND_civic_address', ['FULL_CIVIC', 'STR_NAME', 'STR_TYPE', 'GSA_NAME']);

    if (featureCivID == -9999) {
        return 'CIV_ID is invalid.'
    }

    // Make sure civ id is valid (found in LND_civic_address)
    var filtered_civics = Filter(civics_featureset, `CIV_ID = ${featureCivID}`);

    if (Count(filtered_civics) == 0) {
        return 'ADDRESS NOT FOUND.'
    }

    else {

        // Get civic information from civic address
        var civic_record = First(filtered_civics);

        return `${civic_record['FULL_CIVIC']} ${civic_record['STR_NAME']} ${civic_record['STR_TYPE']}, ${civic_record['GSA_NAME']}`
    }
}