import os
import arcpy
import ast
import datetime
import warnings

warnings.filterwarnings("ignore", message=".*Data Validation extension is not supported.*")

from gispy import (
    connections,
    attribute_rules
)

from gispy.replicas import replicas

from configparser import ConfigParser

from gispy.subtypes import create_subtype
from gispy.domains import transfer_domains, domains_in_db

from gispy.SpatialDataSubmissionForms.features import Feature
from gispy.SpatialDataSubmissionForms.reporter import FieldsReport, DomainsReport

from gispy.metadata.metadata import SDSFMetaData, update_metadata

arcpy.env.overwriteOutput = True
arcpy.SetLogHistory(False)

MAX_TABLE_NAME_LENGTH = 27

config = ConfigParser()
config.read('config.ini')

feature_config = ConfigParser()
feature_config.optionxform = str  # preserve case
# TODO: UPDATE
feature_config.read('feature_config.ini')

SDSF = feature_config.get("SDSF_SETTINGS", "sdsf")
SDSF_IGNORE_FIELDS = ast.literal_eval(feature_config.get("SDSF_SETTINGS", "SDSF_IGNORE_FIELDS"))

ADD_EDITOR_TRACKING = feature_config.getboolean("FEATURE_SETTINGS", "add_editor_tracking")
ENABLE_ARCHIVING = feature_config.getboolean("FEATURE_SETTINGS", "enable_archiving")
EDIT_PERMISSIONS_USERS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "EDIT_PERMISSIONS_USERS"))

READY_TO_ADD_TO_REPLICA = feature_config.getboolean("FEATURE_SETTINGS", "ready_to_add_to_replica")
REPLICA_NAME = feature_config.get("FEATURE_SETTINGS", "replica_name")

SUBTYPES = feature_config.getboolean("FEATURE_SETTINGS", "subtypes")
SUBTYPE_FIELD = feature_config.get("FEATURE_SETTINGS", "subtype_field", fallback="")
SUBTYPE_DOMAINS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "subtype_domains"))  # if needed

TOPOLOGY_DATASET = feature_config.getboolean("FEATURE_SETTINGS", "topology_dataset")

# Optional alias override. If blank, uses 'Alias: ...' from the SDSF, then the METADATA Data Source Name
ALIAS = feature_config.get("FEATURE_SETTINGS", "alias", fallback="").strip()

# UNIQUE ID FIELDS - get a sequence, attribute rule (RW/.gdb only) and an attribute index
UNIQUE_ID_FIELDS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "unique_id_fields", fallback="[]"))

# INDEX FIELDS - attribute index only
INDEX_FIELDS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "index_fields", fallback="[]"))

ALL_INDEX_FIELDS = [x.get("field") for x in UNIQUE_ID_FIELDS if x.get("field")] + INDEX_FIELDS

NEW_DOMAIN_TYPES = dict(feature_config.items("NEW_DOMAIN_TYPES"))
VALID_FIELD_TYPES = {"TEXT", "SHORT", "LONG", "FLOAT", "DOUBLE", "DATE"}

for domain, field_type in NEW_DOMAIN_TYPES.items():

    if field_type.upper() not in VALID_FIELD_TYPES:
        raise ValueError(f"Error: Field type '{field_type}' for domain '{domain}' is not standard.")

PROD_SDE = config.get("SERVER", "prod_rw")

SPATIAL_REFERENCE = os.path.join(PROD_SDE, "SDEADM.LND_hrm_parcel_parks", "SDEADM.LND_hrm_park")

RO_USERS = ["PUBLIC", "SDE"]


def sort_key_description(row):
    description = row[2]

    if description is None:
        return 2, ""

    try:
        return 0, int(description)

    except (TypeError, ValueError):
        return 1, str(description.strip())


def add_indexes(feature, fields):

    for id_field in fields:
        print(f"\nAdding attribute index on {id_field}...")

        try:
            arcpy.AddIndex_management(
                in_table=feature,
                fields=id_field,
                index_name=f"index_{id_field}",
                ascending="ASCENDING"
            )

        except arcpy.ExecuteError:
            arcpy_msg = arcpy.GetMessages(2)
            print(arcpy_msg)


def update_alias(feature, alias):

    if not alias:
        return

    current_alias = arcpy.Describe(feature).aliasName

    if current_alias != alias:
        print(f"\nUpdating alias of '{feature}' from '{current_alias}' to '{alias}'...")
        arcpy.AlterAliasName(feature, alias)


def grant_read_only_privileges(feature):

    for user in RO_USERS:
        print(f"\nGranting view privileges on '{feature}' to {user}...")
        arcpy.ChangePrivileges_management(
            in_dataset=feature,
            user=user,
            View="GRANT"
        )


if __name__ == "__main__":

    if ADD_EDITOR_TRACKING:
        SDSF_IGNORE_FIELDS.extend(["ADDBY", "ADDDATE", "MODBY", "MODDATE"])

    CURRENT_DIR = os.getcwd()

    # RW: creates the feature in RW, then copies it to RO (web_ro gets processed as its own db)
    # RO / web_ro: creates the feature directly in that db, un-versioned, no replica
    for dbs in [
        [
            # config.get("SERVER", "dev_rw"),
            config.get("SERVER", "dev_ro"),
            config.get("SERVER", "dev_web_ro_gdb"),
        ],
        # 
        # [
        #     config.get("SERVER", "qa_rw"),
        #     config.get("SERVER", "qa_ro"),
        #     config.get("SERVER", "qa_web_ro_gdb"),
        # ],
        # 
        # [
        #     config.get("SERVER", "prod_rw"),
        #     config.get("SERVER", "prod_ro"),
        #     config.get("SERVER", "prod_web_ro_gdb"),
        # ],

    ]:

        for count, db in enumerate(dbs, start=1):
            print(f"\n{count}/{len(dbs)}) Database: {db}")

            # Determine the type and read-write status of a database. Ex) SDE + RW, SDE + RO, GDB, etc.
            db_type, db_rights = connections.connection_type(db)

            if not db_type:
                print(f"\tCould not determine the database type of '{db}' - skipping.")
                continue

            for xl_file in [
                SDSF,
            ]:
                print(f"\nCreating feature from {xl_file}...")
                fields_report = FieldsReport(xl_file)

                feature_name = fields_report.feature_class_name  # Should be all lower case except for the prefix
                feature_shape = fields_report.feature_shape

                if feature_shape.upper() == "LINE":
                    feature_shape = "Polyline"

                # Tables without geometry are named in all capitals, feature classes keep the SDSF casing
                is_table = feature_shape.upper() in ("ENTERPRISE GEODATABASE TABLE", "NOT APPLICABLE")

                if is_table:
                    feature_name = feature_name.upper()

                # Don't need to add to WEB if feature is a table
                if db_type == "GDB" and db_rights == "RO" and feature_shape.upper() == "ENTERPRISE GEODATABASE TABLE":
                    print(f"\nFeature is a table - skipping adding to WEB RO...")
                    continue

                field_data = fields_report.field_details

                # Only read domains that are assigned to fields (skips code lookups handled in an ETL)
                field_domains = [str(x).strip() for x in field_data["Domain"] if x and str(x).strip()]

                domains_report = DomainsReport(xl_file, field_domains=field_domains)

                domain_names, domain_dataframes = domains_report.domain_names, domains_report.domain_data

                # Check field names before creating anything (ex. reserved words like USE)
                invalid_fields = dict()

                for field_name in field_data["Field Name"]:
                    field_name = str(field_name).upper().strip()

                    if field_name in SDSF_IGNORE_FIELDS:
                        continue

                    valid_name = arcpy.ValidateFieldName(field_name, db)

                    if valid_name.upper() != field_name:
                        invalid_fields[field_name] = valid_name

                if invalid_fields:
                    raise ValueError(
                        f"Invalid field name(s) for {db}: "
                        f"{', '.join(f'{k} (suggested: {v})' for k, v in invalid_fields.items())}"
                    )

                # Read metadata from the SDSF "METADATA" sheet
                update_options = None
                dataset_name = None

                try:

                    sdsf_meta = SDSFMetaData(xl_file)
                    dataset_name = sdsf_meta.name.replace("METADATA: ", "").strip()
                    today = datetime.datetime.today().strftime("%Y-%m-%dT00:00:00")

                    update_options = {
                        "title": ALIAS or fields_report.alias or dataset_name,
                        "description": str(sdsf_meta.description) if sdsf_meta.description else None,
                        "summary": str(sdsf_meta.summary) if sdsf_meta.summary else None,
                        "tags": str(sdsf_meta.tags) if sdsf_meta.tags else None,
                        "access_constraints": str(sdsf_meta.limitations) if sdsf_meta.limitations else None,
                        "revised_date": today,
                    }
                    print(f"\nSDSF metadata loaded: '{dataset_name}'")

                except Exception as e:
                    print(f"\nWarning: could not read SDSF metadata sheet: {e}")

                # Alias from feature_config.ini, then DATASET DETAILS ('Alias: ...' beside the name),
                # then the METADATA name
                feature_alias = ALIAS or fields_report.alias or dataset_name
                print(f"\nFeature alias: '{feature_alias}'")

                if db_type == "GDB" or db_rights == "RO":

                    # Transfer existing domains from prod and find new domains not in SDE
                    new_domains = transfer_domains(
                        domains=domain_names,
                        output_workspace=db,
                        from_workspace=PROD_SDE
                    ).get("unfound_domains")

                else:
                    # Check for new domains not found in sde
                    domains_in_sde, new_domains, db_domains = domains_in_db(db, domain_names)

                # Create any new domains
                if new_domains:
                    print(f"\nNew domains to create: {', '.join(new_domains)}")

                    subtype_domain_names = {d["domain"] for d in
                                            SUBTYPE_DOMAINS["domains"]} if SUBTYPE_DOMAINS else set()

                    for domain in new_domains:

                        try:
                            field_type = "TEXT"

                            if domain in NEW_DOMAIN_TYPES:
                                field_type = NEW_DOMAIN_TYPES.get(domain)

                            # Check if domain is a subtype domain
                            if domain in subtype_domain_names:
                                field_type = "LONG"
                                print("\t*Subtype Domain Found!")

                            print(f"\n\tCreating domain '{domain}'...")
                            arcpy.CreateDomain_management(
                                in_workspace=db,
                                domain_name=domain,
                                field_type=field_type,
                                domain_type="CODED",
                                domain_description="",
                                split_policy="DUPLICATE"
                            )
                            # Sometimes this says it 'fails', but domain still gets created

                        except arcpy.ExecuteError:
                            arcpy_msg = arcpy.GetMessages(2)
                            print(f"Arcpy Error: {arcpy_msg}")
                            print(f"^^^*(Sometimes this fails in the script, but domain still gets created.)")

                        domain_df = domain_dataframes.get(domain)

                        sort_key = (lambda x: x.Code) if domain in subtype_domain_names else sort_key_description

                        # TypeError: '<' not supported between instances of 'str' and 'int' (LND_fac_snow_group_type)
                        for row in sorted([x for x in domain_df.itertuples()], key=sort_key):
                            code = row[1]
                            desc = row[2]

                            print(f"\tAdding ({code}: {desc})")
                            arcpy.AddCodedValueToDomain_management(
                                in_workspace=db,
                                domain_name=domain,
                                code=code,
                                code_description=desc
                            )

                else:
                    print("\nNO new domains to create.")

                # Create the feature and add fields
                new_feature = Feature(
                    workspace=db,
                    feature_name=feature_name,
                    geometry_type=feature_shape,
                    spatial_reference=SPATIAL_REFERENCE,
                    alias=feature_alias or "#"
                )

                # Feature may have already existed with a different alias
                update_alias(new_feature.feature, feature_alias)

                print("\nAdding Fields...")

                # to_dict keeps blank cells as None (iterrows can turn them into NaN)
                for row in field_data.to_dict("records"):

                    field_name = row["Field Name"].upper().strip()
                    field_length = row["Field Length"]

                    if field_name not in SDSF_IGNORE_FIELDS:
                        alias = row["Alias"]
                        field_type = row["Field Type"]
                        default_value = row["Default Value"]
                        domain = row["Domain"] or "#"

                        if field_length:
                            field_length = int(field_length)

                        if field_type == "TEXT" and not field_length:
                            raise ValueError(
                                f"Field {field_name} of type {field_type} needs to have a field length.")

                        if domain != "#":
                            print(f"\t\t{field_name} has domain: '{domain}'")

                        # Domain is assigned when the field is added
                        new_feature.add_field(
                            field_name=field_name,
                            field_type=field_type,
                            length=field_length,
                            alias=alias,
                            domain_name=domain
                        )

                        # Apply default values for fields, if applicable
                        if default_value:
                            new_feature.add_field_default(
                                field=field_name,
                                default_value=default_value
                            )

                # ADD GLOBAL IDS
                new_feature.add_globalids()

                if ADD_EDITOR_TRACKING:
                    # ADD EDITOR TRACKING FIELDS - all dbs so the schemas match (only enabled where edits happen)
                    new_feature.add_editor_tracking_fields()

                # Update Privileges
                if db_type == "SDE" and db_rights == "RW":
                    new_feature.change_privileges(
                        user="PUBLIC",
                        view="GRANT"
                    )

                    for user in EDIT_PERMISSIONS_USERS:
                        print(f"\nEnabling privileges for {user}")
                        new_feature.change_privileges(
                            user=user,
                            view="GRANT",
                            edit="GRANT"
                        )

                elif db_type == "SDE" and db_rights == "RO":
                    grant_read_only_privileges(new_feature.feature)

                # SUBTYPES
                if SUBTYPES:
                    create_subtype(new_feature.feature, SUBTYPE_FIELD, SUBTYPES, SUBTYPE_DOMAINS)

                if db_type == "SDE" and db_rights == "RO":

                    if READY_TO_ADD_TO_REPLICA:
                        print("\nReplicas need a RW feature - skipping adding to replica.")

                    if ENABLE_ARCHIVING:
                        print("\nArchiving is only enabled on RW features - skipping archiving.")

                if db_type == "SDE" and db_rights == "RW":

                    # Register as Versioned
                    new_feature.register_as_versioned()  # needs to be versioned to add to replica

                    if ENABLE_ARCHIVING:
                        new_feature.enable_archiving()

                    # COPY FEATURE TO RO
                    ro_sdeadm_db = db.replace("RW", "RO")

                    ro_sdeadm_feature = os.path.join(ro_sdeadm_db, new_feature.feature_name)

                    for ro_feature, ro_db in [(ro_sdeadm_feature, ro_sdeadm_db)]:

                        # Tables are not copied to RO
                        if feature_shape.upper() == 'ENTERPRISE GEODATABASE TABLE':
                            print(f"\nFeature is a table - skipping adding to RO...")
                            continue

                        if not arcpy.Exists(ro_feature):
                            print(f"\tCopying RW feature to {ro_db}...")

                            # Keep the RW casing (already all capitals if a table)
                            out_name = new_feature.feature_name.split(".")[-1]

                            if is_table:

                                feature = arcpy.TableToTable_conversion(
                                    in_rows=new_feature.feature,
                                    out_path=ro_db,
                                    out_name=out_name
                                )[0]

                            else:

                                feature = arcpy.FeatureClassToFeatureClass_conversion(
                                    in_features=new_feature.feature,
                                    out_path=ro_db,
                                    out_name=out_name,
                                )[0]

                    if READY_TO_ADD_TO_REPLICA:
                        replicas.add_to_replica(
                            replica_name=REPLICA_NAME,
                            rw_sde=db,
                            ro_sde=ro_sdeadm_db,
                            add_features=[new_feature.feature],
                            topology_dataset=TOPOLOGY_DATASET
                        )

                    # Un-version RO feature, disable editor tracking, index
                    for feature in [ro_sdeadm_feature]:

                        if arcpy.Exists(feature):  # RO feature may not have ever gotten created if it was a table.

                            print(f"\tRegistering as UN-versioned for '{feature}'...")
                            arcpy.UnregisterAsVersioned_management(in_dataset=feature)

                            if ADD_EDITOR_TRACKING:
                                print(f"\tDisabling Editor Tracking for '{feature}'...")
                                arcpy.DisableEditorTracking_management(in_dataset=feature)

                            grant_read_only_privileges(feature)

                            add_indexes(feature, ALL_INDEX_FIELDS)

                            update_alias(feature, feature_alias)

                            # Update metadata on RO copy
                            if update_options:

                                print(f"\nUpdating metadata for RO feature '{new_feature.feature_name}'...")

                                try:
                                    update_metadata(ro_sdeadm_db, new_feature.feature_name, update_options)

                                except Exception as e:
                                    print(f"Warning: RO metadata update failed: {e}")

                # Editor tracking - after feature has been copied to RO. Not on web RO, which is a copy of RO
                if ADD_EDITOR_TRACKING and not (db_type == "GDB" and db_rights == "RO"):
                    # ENABLE EDITOR TRACKING
                    new_feature.enable_editor_tracking()

                # Attribute rules - RW and .gdb only
                if db_rights in ("RW", ""):

                    for field_info in UNIQUE_ID_FIELDS:

                        id_field = field_info.get("field")
                        prefix = field_info.get("prefix")

                        print(f"Creating Sequence and Attribute Rule for {id_field} with prefix {prefix}...")

                        attribute_rules.add_sequence_rule(
                            workspace=db,
                            feature_name=new_feature.feature,
                            field_name=id_field,
                            sequence_prefix=prefix,
                        )

                add_indexes(new_feature.feature, ALL_INDEX_FIELDS)

                # Update metadata on the newly created feature
                if update_options:

                    fc_name = (
                        new_feature.feature_name.split(".")[-1]
                        if db.lower().endswith(".gdb")
                        else new_feature.feature_name
                    )

                    print(f"\nUpdating metadata for '{fc_name}'...")

                    try:
                        update_metadata(db, fc_name, update_options)

                    except Exception as e:
                        print(f"Warning: metadata update failed: {e}")

    # Checks:
    # Replicas
    # Indexes
    # Attribute Rules
    # Default values
    # Domains
    # Privileges assigned
    # Versioned
    # Editor Tracking
    # Features in RO, WEB_RO

    # Add to CMDB
