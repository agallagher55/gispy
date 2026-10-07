import functools
import os
import time

import arcpy

try:
    from gispy import locks
except ImportError:
    import locks

arcpy.env.overwriteOutput = True

EDITOR_TRACKING_FIELD_INFO = {
    "ADDBY": {
        "field_type": "TEXT",
        "field_length": 32,
        "field_alias": "Add By"
    },
    "MODBY": {
        "field_type": "TEXT",
        "field_length": 32,
        "field_alias": "Modified By"
    },
    "ADDDATE": {
        "field_type": "DATE",
        "field_length": "",
        "field_alias": "Add Date"
    },
    "MODDATE": {
        "field_type": "DATE",
        "field_length": "",
        "field_alias": "Modified Date"
    },
}


def arcpy_messages(func):

    @functools.wraps(func)
    def wrapper(*args, **kwargs):

        try:
            result = func(*args, **kwargs)
            messages = arcpy.GetMessages()
            message_lines = messages.split("\n")

            for message in message_lines:
                if message:
                    print(f"\t{message}")

            return result

        except arcpy.ExecuteError as e:
            # Arguments the failing call was made with (skip 'self')
            call_args = [f"{a!r}" for a in args[1:]] + [f"{k}={v!r}" for k, v in kwargs.items()]

            # Error messages only, each once (the exception text repeats them)
            error_lines = [x.strip() for x in arcpy.GetMessages(2).splitlines() if x.strip()]

            print(f"\n\tARCPY ERROR in {func.__name__}({', '.join(call_args)})")

            for line in error_lines:
                print(f"\t    {line}")

            print()

    return wrapper
    

class Feature:
    def __init__(self, workspace, feature_name: str, geometry_type, spatial_reference=None, alias: str = "#"):
        self.workspace = workspace
        self.feature_name = feature_name
        self.geometry_type = geometry_type
        self.spatial_reference = spatial_reference
        self.alias = alias

        self.feature = os.path.join(self.workspace, self.feature_name)
        self.fields = set()

        self.create_feature()
        self.desc = arcpy.Describe(self.feature)

    @arcpy_messages
    def create_feature(self):
        print(f"\nCreating {self.geometry_type or ''} feature '{self.feature_name}'...")

        # Check if feature already exists
        if arcpy.Exists(self.feature):
            print("\tFeature already exists!")
            self.fields = {x.name for x in arcpy.ListFields(self.feature)}
            return self.feature

        # Check if feature is a table
        if self.geometry_type.upper() in ("ENTERPRISE GEODATABASE TABLE", "NOT APPLICABLE"):
            arcpy.CreateTable_management(
                out_path=self.workspace,
                out_name=self.feature_name,
                out_alias=self.alias
            )

        else:
            if not self.spatial_reference:
                raise ValueError(f"Please provide a spatial reference for this feature class.")

            arcpy.CreateFeatureclass_management(
                out_path=self.workspace,
                out_name=self.feature_name,
                geometry_type=self.geometry_type,
                spatial_reference=self.spatial_reference,
                out_alias=self.alias
            )
            print(arcpy.GetMessages())

        self.fields = {x.name for x in arcpy.ListFields(self.feature)}
        print(f"\t{self.geometry_type} feature Created.")

        return self.feature

    def ensure_schema_lock(
            self, unlock: bool = False, admin_workspace: str = None, retries: int = 5, wait_seconds: int = 2
    ) -> bool:
        """
        Check that a schema lock can be acquired on this feature, optionally clearing the locks that block it.

        Sessions holding the lock are reported using locks.get_feature_locks(). When unlock is True and the workspace
        is an SDE connection, those sessions are disconnected using locks.remove_locks(). If no session can be matched
        to the lock (e.g. missing VIEW SERVER STATE permission), remove_locks() falls back to disconnecting all
        sessions on the connection, so only use unlock=True against a database where that is acceptable.

           :param unlock: Disconnect the sessions holding the lock
           :param admin_workspace: SDE connection file for the geodatabase administrator (sde user). Listing and
                                   disconnecting sessions requires admin rights, which a data owner connection
                                   such as SDEADM does not have. Defaults to the feature's own workspace.
           :param retries: Number of times to re-test the lock after disconnecting sessions
           :param wait_seconds: Seconds to wait between re-tests
           :return: True if a schema lock is available
           """

        if arcpy.TestSchemaLock(self.feature):
            return True

        print(f"\tWARNING: cannot get a schema lock on '{self.feature_name}'.")

        if self.workspace.lower().endswith(".gdb"):
            print("\tFile geodatabase: close any other app (ArcGIS Pro, ArcMap, ArcCatalog) using this data.")
            return False

        sde_admin = admin_workspace or self.workspace

        if not admin_workspace and unlock:
            print("\tNo admin connection provided, using the feature's connection (may not have admin rights).")

        holders = locks.get_feature_locks(sde_admin, self.feature_name)

        for row in holders:
            print(
                f"\t    sde_id={row['sde_id']}  user={row['username']}  machine={row['client_name']}  "
                f"type={row['client_type']}  lock={row['lock_type']}"
            )

        if not holders:
            print("\t    No specific session could be matched to the lock.")
            self._print_sessions(sde_admin, "Connected sessions")

        if not unlock:
            print("\tTip: pass unlock=True to disconnect the sessions holding the lock.")
            return False

        print("\tAttempting to remove locks...")
        try:
            locks.remove_locks(sde_admin, feature=self.feature_name, dry_run=False)

        except (arcpy.ExecuteError, RuntimeError) as e:
            print(f"\tERROR: could not remove locks: {e}")
            print("\tProvide an admin (sde user) connection file via admin_workspace, or stop the service manually.")
            return False

        for attempt in range(1, retries + 1):
            if arcpy.TestSchemaLock(self.feature):
                print("\tSchema lock is now available.")
                return True

            print(f"\tStill locked, re-testing ({attempt}/{retries})...")
            time.sleep(wait_seconds)

        print("\tERROR: schema lock could not be cleared.")
        self._print_sessions(sde_admin, "Sessions still connected after disconnect")
        print(
            "\tIf sessions keep coming back, a published service is likely reconnecting. "
            "Stop the service that uses this feature, then re-run."
        )
        return False

    @staticmethod
    def _print_sessions(sde_workspace: str, label: str):
        """Print every session connected to an SDE workspace (needs an admin connection)."""

        try:
            sessions = arcpy.ListUsers(sde_workspace)

        except Exception as e:
            print(f"\t    Could not list sessions: {e}")
            return

        print(f"\t    {label} ({len(sessions)}):")

        for user in sessions:
            print(
                f"\t      sde_id={user.ID}  user={user.Name}  machine={user.ClientName}  "
                f"type={getattr(user, 'ClientType', None)}  minutes={user.MinutesConnected}  "
                f"transactions={user.TransactionCount}"
            )

    @arcpy_messages
    def add_field(
            self, field_name: str, field_type: str, length: int, alias: str, domain_name: str, precision="#",
            unlock: bool = False, admin_workspace: str = None
    ):
        """
        Although the Field object's type property values are not an exact match for the keywords used by the Add Field
        tool's field_type parameter, all of the Field object's type values can be used as input to this parameter.
        The different field types are mapped as follows: Integer to LONG, String to TEXT, and SmallInteger to SHORT.

           :param field_name:
           :param field_type:
           :param length:
           :param alias:
           :param nullable:
           :param domain_name:
           :param unlock: If a schema lock blocks the edit, disconnect the SDE sessions holding it
           :param admin_workspace: SDE admin (sde user) connection file used to list and disconnect sessions
           :return:
           """

        # If field already exists, skip
        if field_name in self.fields:
            print(f"\t'{field_name}' already exists in {self.feature_name}")
            return True

        FIELD_REQUIRED = "NON_REQUIRED"
        valid_types = ["TEXT", "FLOAT", "DOUBLE", "SHORT", "LONG", "DATE", "DATEONLY", "TIMEONLY"]

        if field_type:
            field_type = field_type.upper()

        if field_type == "STRING":
            field_type = "TEXT"

        if field_type not in valid_types:
            print(f"Field Type: {field_type}")
            raise ValueError(f"Field type: '{field_type}' does not appear to be a valid field type!")

        # if field_type == "SHORT":
        #     field_precision = input("Please provide field precision: ")
        #
        # else:
        #     field_precision = "#"  # int

        # Pre-checks so the most common causes of ERROR 000852 are reported clearly
        domain_name = (domain_name or "").strip()

        if domain_name:
            domains = {d.name: d for d in arcpy.da.ListDomains(self.workspace)}

            if domain_name not in domains:
                raise ValueError(f"Domain '{domain_name}' does not exist in workspace '{self.workspace}'.")

            domain_field_type = domains[domain_name].type
            print(f"\tDomain '{domain_name}' found (field type: {domain_field_type}).")

        # Schema locks are another common cause of ERROR 000852 on SDE
        self.ensure_schema_lock(unlock=unlock, admin_workspace=admin_workspace)

        print(
            f"\tAdding field: name='{field_name}', type={field_type}, length={length}, "
            f"alias='{alias}', domain='{domain_name}'"
        )

        arcpy.AddField_management(
            in_table=self.feature,
            field_name=field_name.strip(),  # Field Name
            field_type=field_type,  # Field Type
            field_precision=precision,
            field_scale="#",
            field_length=length,  # Field Length (# of characters)
            field_alias=alias.strip(),  # Alias
            field_is_nullable="NULLABLE",  # NULLABLE
            field_is_required=FIELD_REQUIRED,  #
            field_domain=domain_name.strip()  # Domain
        )
        self.fields.add(field_name)

    @arcpy_messages
    def change_privileges(self, user: str, view: str = "#", edit: str = "#"):
        """
        :param user: The database username whose privileges are being modified.
        :param view: Establishes the user's view privileges.
                        AS_IS — No change to the user's existing view privilege.
                        If the user has view privileges, they will continue to have view privileges.
                        If the user doesn't have view privileges, they will continue to not have view privileges

                        GRANT —Allows user to view datasets.

                        REVOKE —Removes all user privileges to view datasets.

        :param edit: Establishes the user's edit privileges.
                        AS_IS — No change to the user's existing edit privilege.
                        If the user has edit privileges, they will continue to have edit privileges.
                        If the user doesn't have edit privileges, they will continue to not have edit privileges
                        This is the default.

                        GRANT —Allows the user to edit the input datasets.
                        REVOKE —Removes the user's edit privileges. The user may still view the input dataset.
        :return:
        """

        print(f"\nUpdating privileges to dataset '{self.feature}'...")
        arcpy.ChangePrivileges_management(
            in_dataset=self.feature,
            user=user,
            View=view,
            Edit=edit
        )
        print("\tPrivileges changed.")

    @arcpy_messages
    def register_as_versioned(self, edit_to_base: str = "#"):
        """
        :param edit_to_base: Specifies whether edits made to the default version will be moved to the
                                base tables. This parameter is not applicable for branch versioning.

                            NO_EDITS_TO_BASE — The dataset will not be versioned with the option of moving
                                                edits to base. This is the default.
                            EDITS_TO_BASE — The dataset will be versioned with the option of moving edits to base
        :return:
        """

        print(f"\nRegistering dataset '{self.feature}' as versioned.")
        arcpy.RegisterAsVersioned_management(
            self.feature,
            edit_to_base
        )
        print("\tDataset registered.")

    @arcpy_messages
    def add_editor_tracking_fields(self, field_info=EDITOR_TRACKING_FIELD_INFO):
        """    
        The enable_editor_tracking function enables editor tracking on a feature class.

        :param creator_field: str: Specify the field that will store the name of the user who created a record
        :param creation_date_field: str: Specify the name of the field that will store creation dates
        :param last_editor_field: str: Define the field name that will be used to store the user who last edited a feature
        :param last_edit_date_field: str: Determine the field name that will store the last edit date
        :param add_fields: str: Determine whether or not to add the fields
        :param record_dates_in: str: Specify the time zone in which to record dates
        :return: A boolean value
        """

        print(f"\nAdding Editor Tracking fields to '{self.feature}'...")

        for field in field_info:
            if field not in self.fields:
                print(f"\tAdding '{field}' field...")

                field_type = field_info[field]["field_type"]
                field_length = field_info[field]["field_length"]
                field_alias = field_info[field]["field_alias"]

                arcpy.AddField_management(self.feature, field, field_type, "", "", field_length, field_alias)
                self.fields.add(field)

    @arcpy_messages
    def enable_editor_tracking(self, creator_field: str = "ADDBY", creation_date_field: str = "ADDDATE",
                               last_editor_field: str = "MODBY", last_edit_date_field: str = "MODDATE",
                               add_fields: str = "NO_ADD_FIELDS", record_dates_in: str = "UTC"):

        print(f"\nApplying editor tracking to {self.feature}...")

        if self.desc.editorTrackingEnabled:
            print(f"\t{self.feature} already had Editor Tracking Enabled!")

        arcpy.EnableEditorTracking_management(
            self.feature,
            creator_field,
            creation_date_field,
            last_editor_field,
            last_edit_date_field,
            add_fields,
            record_dates_in
        )

    @arcpy_messages
    def add_globalids(self):
        print(f"\nAdding GlobalIDs to '{self.feature}'...")

        if "GlobalID" in self.fields:
            print(f"{self.feature} already has a GlobalID field.")
            return True

        arcpy.AddGlobalIDs_management(self.feature)

    @arcpy_messages
    def add_field_default(self, field: str, default_value):
        print(f"\nAssigning default value of '{default_value}' to {field}...")

        # Check if field already has default applied.
        try:
            current_default = [x.defaultValue for x in arcpy.ListFields(self.feature) if x.name == field][0]
            if current_default == default_value:
                return default_value

            arcpy.AssignDefaultToField_management(
                in_table=self.feature,
                field_name=field,
                default_value=default_value
            )
        except IndexError as e:
            print(e)
            print(f"Did not find {field} in {self.feature_name}")

    @arcpy_messages
    def enable_archiving(self):
        print(f"\nEnabling archiving on '{self.feature}'...")

        if self.desc.isArchived:
            print(f"\t'{self.feature}' already has archiving enabled.")
            return

        arcpy.EnableArchiving_management(self.feature)
        print("\tArchiving enabled.")

    @arcpy_messages
    def assign_domain(self, field_name, domain_name, subtypes="#"):
        print(f"\nAssigning domain '{domain_name}' to field '{field_name}'...")

        # TODO: Check if field already has domain assigned.

        arcpy.AssignDomainToField_management(
            in_table=self.feature,
            field_name=field_name,
            domain_name=domain_name,
            subtype_code=subtypes  # Optional
        )

    @arcpy_messages
    def remove_domain(self, field_name, subtypes="#"):
        print(f"\nRemoving domain from field '{field_name}' on '{self.feature_name}'...")

        arcpy.RemoveDomainFromField_management(
            in_table=self.feature,
            field_name=field_name,
            subtype_code=subtypes
        )


class Table(Feature):
    def __init__(self, workspace, feature_name: str, alias: str = "#"):
        # workspace, feature_name: str, geometry_type, spatial_reference, alias: str = "#"

        self.geometry_type = None
        self.spatial_reference = None

        super(Table, self).__init__(
            workspace=workspace,
            feature_name=feature_name,
            geometry_type=self.geometry_type,
            feature_dataset=None,
            spatial_reference=self.spatial_reference,
            alias=alias,
        )
