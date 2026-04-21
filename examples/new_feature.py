import os
import ast
import datetime

import arcpy

from gispy import (
    connections,
    attribute_rules
)
from gispy.utils import setupLog

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
feature_config.read('feature_config_hwa_tree.ini')

log_file = os.path.join(os.getcwd(), f"{datetime.date.today()}_new_feature.log")
logger = setupLog(log_file, log_to_console=True)

SDSF = feature_config.get("SDSF_SETTINGS", "sdsf")
SDSF_IGNORE_FIELDS = ast.literal_eval(feature_config.get("SDSF_SETTINGS", "SDSF_IGNORE_FIELDS"))

ADD_EDITOR_TRACKING = feature_config.getboolean("FEATURE_SETTINGS", "add_editor_tracking")
ENABLE_ARCHIVING = feature_config.getboolean("FEATURE_SETTINGS", "enable_archiving")
EDIT_PERMISSIONS_USERS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "EDIT_PERMISSIONS_USERS"))

READY_TO_ADD_TO_REPLICA = feature_config.getboolean("FEATURE_SETTINGS", "ready_to_add_to_replica")
REPLICA_NAME = feature_config.get("FEATURE_SETTINGS", "replica_name")

SUBTYPES = feature_config.getboolean("FEATURE_SETTINGS", "subtypes")
SUBTYPE_FIELD = feature_config.get("FEATURE_SETTINGS", "subtype_field", fallback="")
SUBTYPE_DOMAINS = ast.literal_eval(feature_config.get("FEATURE_SETTINGS", "subtype_domains"))

TOPOLOGY_DATASET = feature_config.getboolean("FEATURE_SETTINGS", "topology_dataset")

UNIQUE_ID_FIELDS = ast.literal_eval(
    feature_config.get('FEATURE_SETTINGS', "unique_id_fields", fallback='[]'))

# TODO: UPDATE
NEW_DOMAIN_TYPES = dict(feature_config.items("NEW_DOMAIN_TYPES"))
VALID_FIELD_TYPES = {"TEXT", "SHORT", "LONG", "FLOAT", "DOUBLE", "DATE"}

for domain, field_type in NEW_DOMAIN_TYPES.items():
    if field_type.upper() not in VALID_FIELD_TYPES:
        raise ValueError(f"Error: Field type '{field_type}' for domain '{domain}' is not standard.")

PROD_SDE = config.get("SERVER", "prod_rw")

SPATIAL_REFERENCE = os.path.join(PROD_SDE, "SDEADM.LND_hrm_parcel_parks", "SDEADM.LND_hrm_park")


def sort_key_description(row):

    description = row[2].strip()  # Description column — positional to handle "Description" vs "DESCRIPTION" headers

    if description is None:
        return 2, ""

    try:
        return 0, int(description)

    except (TypeError, ValueError):
        return 1, str(description)


if __name__ == "__main__":

    if ADD_EDITOR_TRACKING:
        SDSF_IGNORE_FIELDS.extend(["ADDBY", "ADDDATE", "MODBY", "MODDATE"])

    CURRENT_DIR = os.getcwd()

    for dbs in [
        [
            config.get("SERVER", "dev_rw"),
        ],

        # [
        #     config.get("SERVER", "qa_rw"),  # qa_ro, qa_web_ro will get copied to db when processing rw
        # ],

        # [
        #     config.get("SERVER", "prod_rw"),
        # ],

    ]:

        for count, db in enumerate(dbs, start=1):
            logger.info(f"{count}/{len(dbs)}) Database: {db}")

            # Determine the type and read-write status of a database. Ex) SDE + RW, SDE + RO, GDB, etc.
            db_type, db_rights = connections.connection_type(db)

            for xl_file in [
                SDSF,
            ]:
                logger.info(f"Creating feature from {xl_file}...")
                fields_report = FieldsReport(xl_file)

                feature_name = fields_report.feature_class_name  # Should be all lower case except for the prefix
                feature_shape = fields_report.feature_shape

                if feature_shape.upper() == "LINE":
                    feature_shape = "Polyline"

                field_data = fields_report.field_details

                domains_report = DomainsReport(xl_file)

                domain_names, domain_dataframes = domains_report.domain_info()

                # Read metadata from the SDSF "METADATA" sheet
                update_options = None

                try:
                    sdsf_meta = SDSFMetaData(xl_file)
                    dataset_name = sdsf_meta.name.replace("METADATA: ", "").strip()
                    today = datetime.datetime.today().strftime("%Y-%m-%dT00:00:00")

                    update_options = {
                        "title": dataset_name,
                        "description": str(sdsf_meta.description) if sdsf_meta.description else None,
                        "summary": str(sdsf_meta.summary) if sdsf_meta.summary else None,
                        "tags": str(sdsf_meta.tags) if sdsf_meta.tags else None,
                        "access_constraints": str(sdsf_meta.limitations) if sdsf_meta.limitations else None,
                        "revised_date": today,
                    }
                    logger.info(f"SDSF metadata loaded: '{dataset_name}'")

                except Exception as e:
                    logger.warning(f"Could not read SDSF metadata sheet: {e}")

                if db_type == "GDB":

                    # Transfer existing domains to local gdb and find new domains not in SDE
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
                    logger.info(f"New domains to create: {', '.join(new_domains)}")

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
                                logger.info("\t*Subtype Domain Found!")

                            logger.info(f"\tCreating domain '{domain}'...")
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
                            logger.error(f"Arcpy Error: {arcpy_msg}")
                            logger.warning("(Sometimes this fails in the script, but domain still gets created.)")

                        domain_df = domain_dataframes.get(domain)

                        sort_key = (lambda x: x.Code) if domain in subtype_domain_names else sort_key_description

                        # TypeError: '<' not supported between instances of 'str' and 'int' (LND_fac_snow_group_type)
                        for row in sorted([x for x in domain_df.itertuples()], key=sort_key):
                            code = row.Code
                            desc = row.Description

                            logger.info(f"\tAdding ({code}: {desc})")
                            arcpy.AddCodedValueToDomain_management(
                                in_workspace=db,
                                domain_name=domain,
                                code=code,
                                code_description=desc
                            )

                else:
                    logger.info("NO new domains to create.")

                # Create the feature and add fields
                if (db_type == "SDE" and db_rights == "RW") or (db_type == "GDB" and not db_rights):

                    new_feature = Feature(
                        workspace=db,
                        feature_name=feature_name,
                        geometry_type=feature_shape,
                        spatial_reference=SPATIAL_REFERENCE
                    )

                    logger.info("Adding Fields...")
                    feature_fields = field_data["Field Name"].values

                    for row_num, row in field_data.iterrows():

                        field_name = row["Field Name"].upper().strip()
                        field_length = row["Field Length"]

                        if field_name not in SDSF_IGNORE_FIELDS:
                            alias = row["Alias"]
                            field_type = row["Field Type"]
                            nullable = row["Nullable"]
                            default_value = row["Default Value"]
                            domain = row["Domain"] or "#"

                            if field_length:
                                field_length = int(field_length)

                            if field_type == "TEXT" and not field_length:
                                raise ValueError(
                                    f"Field {field_name} of type {field_type} needs to have a field length.")

                            new_feature.add_field(
                                field_name=field_name.upper(),
                                field_type=field_type,
                                length=field_length,
                                alias=alias,
                                # nullable=nullable,
                                domain_name=domain
                            )

                            if domain and domain != "#":
                                logger.info(f"\t\t{field_name} has domain: '{domain}'")
                                new_feature.assign_domain(
                                    field_name=field_name,
                                    domain_name=domain,
                                    subtypes="#"
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
                        # ADD EDITOR TRACKING FIELDS
                        if db_type in ("SDE", "GDB") and db_rights in ("RW", ""):
                            new_feature.add_editor_tracking_fields()

                    # Update Privileges
                    if db_type != "GDB":
                        new_feature.change_privileges(
                            user="PUBLIC",
                            view="GRANT"
                        )

                        for user in EDIT_PERMISSIONS_USERS:
                            logger.info(f"Enabling privileges for {user}")
                            new_feature.change_privileges(
                                user=user,
                                view="GRANT",
                                edit="GRANT"
                            )

                    # SUBTYPES
                    if SUBTYPES:
                        create_subtype(new_feature.feature, SUBTYPE_FIELD, SUBTYPES, SUBTYPE_DOMAINS)

                    if db_type == "SDE" and db_rights == "RW":

                        # Register as Versioned
                        new_feature.register_as_versioned()  # needs to be versioned to add to replica

                        if ENABLE_ARCHIVING:
                            new_feature.enable_archiving()

                        # COPY FEATURE TO RO
                        ro_sdeadm_db = db.replace("RW", "RO")
                        ro_sdeadm_feature = os.path.join(ro_sdeadm_db, new_feature.feature_name)

                        if feature_shape.upper() == 'ENTERPRISE GEODATABASE TABLE':
                            logger.info("Feature is a table - skipping adding to WEB RO...")
                        else:
                            if not arcpy.Exists(ro_sdeadm_feature):
                                logger.info(f"\tCopying RW feature to {ro_sdeadm_db}...")

                                # Need to use table to table if a table...
                                if feature_shape.upper() in ('ENTERPRISE GEODATABASE TABLE', 'NOT APPLICABLE'):
                                    arcpy.TableToTable_conversion(
                                        in_rows=new_feature.feature,
                                        out_path=ro_sdeadm_db,
                                        out_name=new_feature.feature_name
                                    )

                                else:
                                    arcpy.FeatureClassToFeatureClass_conversion(
                                        in_features=new_feature.feature,
                                        out_path=ro_sdeadm_db,
                                        out_name=new_feature.feature_name,
                                    )

                        if READY_TO_ADD_TO_REPLICA:
                            replicas.add_to_replica(
                                replica_name=REPLICA_NAME,
                                rw_sde=db,
                                ro_sde=ro_sdeadm_db,
                                add_features=[new_feature.feature],
                                topology_dataset=TOPOLOGY_DATASET
                            )

                        # Un-version RO feature, disable editor tracking, index
                        if arcpy.Exists(ro_sdeadm_feature):  # may not exist if feature was a table

                            logger.info(f"\tRegistering as UN-versioned for '{ro_sdeadm_feature}'...")
                            arcpy.UnregisterAsVersioned_management(in_dataset=ro_sdeadm_feature)

                            if ADD_EDITOR_TRACKING:
                                logger.info(f"\tDisabling Editor Tracking for '{ro_sdeadm_feature}'...")
                                arcpy.DisableEditorTracking_management(in_dataset=ro_sdeadm_feature)

                            # Set privileges
                            ro_users = ["PUBLIC", "SDE"]

                            for user in ro_users:
                                arcpy.ChangePrivileges_management(
                                    in_dataset=ro_sdeadm_feature,
                                    user=user,
                                    View="GRANT"
                                )

                            for field_info in UNIQUE_ID_FIELDS:
                                id_field = field_info.get("field")

                                logger.info(f"Adding attribute index on {id_field}...")
                                try:
                                    arcpy.AddIndex_management(
                                        in_table=ro_sdeadm_feature,
                                        fields=id_field,
                                        index_name=f"index_{id_field}",
                                        ascending="ASCENDING"
                                    )

                                except arcpy.ExecuteError:
                                    arcpy_msg = arcpy.GetMessages(2)
                                    logger.error(arcpy_msg)

                            # Update metadata on RO copy
                            if update_options:
                                logger.info(f"Updating metadata for RO feature '{new_feature.feature_name}'...")
                                try:
                                    update_metadata(ro_sdeadm_db, new_feature.feature_name, update_options)
                                except Exception as e:
                                    logger.warning(f"RO metadata update failed: {e}")

                    if ADD_EDITOR_TRACKING:
                        # ENABLE EDITOR TRACKING
                        new_feature.enable_editor_tracking()

                    # Attribute Rules - Add after feature has been copied to Read-Only. RW and .gdb only
                    for field_info in UNIQUE_ID_FIELDS:

                        id_field = field_info.get("field")
                        prefix = field_info.get("prefix")

                        logger.info(f"Creating Sequence and Attribute Rule for {id_field} with prefix {prefix}...")

                        attribute_rules.add_sequence_rule(
                            workspace=db,
                            feature_name=new_feature.feature,
                            field_name=id_field,
                            sequence_prefix=prefix,
                        )

                        logger.info(f"Adding attribute index on {id_field}...")
                        try:
                            arcpy.AddIndex_management(
                                in_table=new_feature.feature,
                                fields=id_field,
                                index_name=f"index_{id_field}",
                                ascending="ASCENDING"
                            )

                        except arcpy.ExecuteError:
                            arcpy_msg = arcpy.GetMessages(2)
                            logger.error(arcpy_msg)

                    # Update metadata on the newly created RW/GDB feature
                    if update_options:

                        fc_name = (
                            new_feature.feature_name.split(".")[-1]
                            if db.lower().endswith(".gdb")
                            else new_feature.feature_name
                        )

                        logger.info(f"Updating metadata for '{fc_name}'...")

                        try:
                            update_metadata(db, fc_name, update_options)

                        except Exception as e:
                            logger.warning(f"Metadata update failed: {e}")

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
