from typing import Tuple

import pandas as pd


class SpatialDataSubmissionFormError(Exception):
    pass


class Report:
    def __init__(self, excel_path, sheet_name="DATASET DETAILS"):
        self.source = excel_path
        self.sheet_name = sheet_name

        self.df = self.to_dataframe(self.sheet_name)
        self.feature_class_name, self.feature_shape, self.feature_type = self.report_details()
        self.alias = self.report_alias()

    def to_dataframe(self, sheet_name, drop_blank_rows=True):
        try:
            df = pd.read_excel(io=self.source, sheet_name=sheet_name, index_col=0)
        except ValueError:
            raise SpatialDataSubmissionFormError(
                f"Sheet '{sheet_name}' not found in '{self.source}'. "
                f"Check that the SDSF follows the expected template."
            )
        df = df.astype(object).where(pd.notnull(df), None)  # Replace NaN values with None (object dtype keeps None)

        if drop_blank_rows:
            df = df[pd.notnull(df.index)]  # Remove blank lines from index

        return df

    def report_details(self):
        df_feature_details = self.df.iloc[0:3, 0:1]  # first col in excel is index - col 0 in df is second col in excel
        df_feature_details = df_feature_details.where(pd.notnull(df_feature_details), None)  # Convert nan to None

        df_feature_details = df_feature_details.T  # Transpose
        df_feature_details.columns = [x.strip(":") for x in df_feature_details.columns]

        # Check for 'Feature Class Name' or 'Data Source Name' column and get the value
        if 'Feature Class Name' in df_feature_details.columns:
            feature_class_name = df_feature_details['Feature Class Name'].values[0]

        elif 'Data Source Name' in df_feature_details.columns:
            feature_class_name = df_feature_details['Data Source Name'].values[0]

        else:
            raise ValueError("Neither 'Feature Class Name' nor 'Data Source Name' column found in the DataFrame")

        shape_type = df_feature_details["Shape Type"].values[0] or "Enterprise Geodatabase Table"
        feature_type = df_feature_details["Feature Type"].values[0]

        return feature_class_name, shape_type, feature_type


    def report_alias(self):
        """Read the alias from the cell beside the Data Source Name, formatted as 'Alias: <alias>'."""

        try:
            value = self.df.iloc[0, 1]

        except IndexError:
            return None

        if pd.isna(value) or not str(value).strip().upper().startswith("ALIAS"):
            return None

        alias = str(value).split(":", 1)[-1].strip()

        return alias or None


class SDSFMetaData:

    def __init__(self, excel_path, sheet_name="SDSF"):
        self.source = excel_path

        try:
            self.df = pd.read_excel(self.source, sheet_name=sheet_name)
        except ValueError:
            raise SpatialDataSubmissionFormError(
                f"Sheet '{sheet_name}' not found in '{self.source}'. "
                f"Check that the SDSF follows the expected template."
            )

        self.name = self.get_name()

        self.description = self.get_description()
        self.summary = self.get_summary()
        self.tags = self.get_tags()

        self.limitations = self.get_limitations()

    def __repr__(self):
        return self.name

    def _get_value_below_header(self, header: str):
        matches = self.df.loc[self.df['Spatial Data Submission Form'] == header].index
        if len(matches) == 0:
            raise SpatialDataSubmissionFormError(
                f"Expected header '{header}' not found in '{self.source}'."
            )
        return self.df.iloc[matches[0] + 1, 0]

    def get_description(self):
        return self._get_value_below_header('Dataset Description:')

    def get_summary(self):
        return self._get_value_below_header('Dataset Purpose:')

    def get_tags(self):
        return self._get_value_below_header('Dataset Tags:')

    def get_limitations(self):
        return self._get_value_below_header('Notes or Disclaimers:')

    def get_name(self):
        matches = self.df.loc[self.df['Spatial Data Submission Form'] == 'Dataset Name:'].index
        if len(matches) == 0:
            raise SpatialDataSubmissionFormError(
                f"Expected header 'Dataset Name:' not found in '{self.source}'."
            )
        return self.df.iloc[matches[0], 1]


class FieldsReport(Report):

    def __init__(self, excel_path, sheet_name="DATASET DETAILS"):
        self.last_field_name = "GLOBALID"
        super().__init__(excel_path, sheet_name)
        self.field_details = self.field_info()

        if "Subtype Field" in [x for x in self.field_details.columns]:
            self.subtype_fields = self.subtype_info()

    def subtype_info(self):
        fields_df = self.field_details

        if "Subtype Field" not in [x for x in fields_df.columns]:
            return ()

        subtype_field_df = fields_df[fields_df["Subtype Field"].notnull()]

        if not subtype_field_df.empty:
            subtype_fields = list(subtype_field_df["Field Name"])
            return subtype_fields

    def field_info(self):
        df_index_values = self.df.index.values.tolist()

        if self.feature_type.upper() == "FEATURE CLASS":
            
            self.last_field_name = "SHAPE_Length"

            if self.feature_shape.upper() == "POLYGON":
                if "SHAPE_AREA" not in [str(x).upper() for x in df_index_values] or "SHAPE_LENGTH" not in [str(x).upper() for x in df_index_values]:
                    raise IndexError(f"ERROR: SDSF needs to have SHAPE_AREA and SHAPE_LENGTH fields.")

            elif self.feature_shape.upper() == "LINE":
                if "SHAPE_LENGTH" not in [str(x).upper() for x in df_index_values]:
                    raise IndexError(f"ERROR: SDSF needs to have a SHAPE_LENGTH field.")

            elif self.feature_shape.upper() == "NOT APPLICABLE" or self.feature_shape.upper() == "POINT":
                self.last_field_name = "GLOBALID"

        df_field_details = self.df.loc["Alias":self.last_field_name]

        df_field_details.reset_index(inplace=True)

        df_field_details.columns = df_field_details.iloc[0]  # Set DataFrame columns as first row
        columns = [x for x in df_field_details.columns if x]

        df_field_details = df_field_details.loc[:, columns]  # Limit columns to columns list

        df_field_details = df_field_details.iloc[1:]  # Ignore columns row as a data row

        return df_field_details

    def domain_fields(self) -> dict:
        domain_fields = self.field_details[["Field Name", "Domain", "Field Type"]][
            ~self.field_details["Domain"].isnull()]

        domain_fields_info = domain_fields.to_dict("records")

        return domain_fields_info


class DomainsReport(Report):
    
    domains_section_header = "Fields with associated codes(values) and descriptions"
    
    def __init__(self, excel_path, subtype_field=(), sheet_name="DATASET DETAILS", field_domains=None):
        """
        :param field_domains: optional list of domain names assigned to fields. When provided, only these
                              domains are read from the domains section (ex. code lookups converted in an ETL
                              and not assigned to a field are skipped).
        """
        super().__init__(excel_path, sheet_name)

        self.subtype_field = subtype_field
        self.field_domains = field_domains

        self.domain_df = pd.DataFrame()

        # Populate domain information on initialization so attributes
        # are immediately available for consuming modules such as
        # SpatialDataSubmissionForms.main
        self.domain_names, self.domain_data = self.domain_info()

    def domain_info(self) -> Tuple[list, dict]:
        """Parse domain information from the SDSF worksheet.

        Returns a tuple of ``(domain_names, domain_data)`` where
        ``domain_names`` is a list of domain names found in the sheet and
        ``domain_data`` is a dictionary mapping those domain names to
        :class:`pandas.DataFrame` objects of coded values.

        Each domain section is a field name / domain name row, a "Code" / "Description" header row, then
        the coded values. A section ends at the first blank row or at the start of the next domain, so notes
        below the domains (ex. queries, lookup tables) are not read as coded values.
        """

        domain_dataframes = dict()

        # Keep blank rows so the end of each domain section can be found
        raw_df = self.to_dataframe(self.sheet_name, drop_blank_rows=False)

        index_labels = [str(x).strip() if pd.notnull(x) else None for x in raw_df.index]

        if DomainsReport.domains_section_header not in index_labels:
            return [], domain_dataframes

        # Get domain info from main spreadsheet - Starts at first row after the domains section header
        section_start = index_labels.index(DomainsReport.domains_section_header) + 1

        self.domain_df = raw_df.iloc[section_start:]
        labels = index_labels[section_start:]

        # Find each domain section - the domain name row is the non-blank row above "Code"
        domain_sections = list()

        for count, label in enumerate(labels):

            if not label or label.upper() != "CODE":
                continue

            name_row = count - 1

            while name_row >= 0 and not labels[name_row]:
                name_row -= 1

            if name_row < 0:
                continue

            domain_name = self.domain_df.iloc[name_row, 0]

            if pd.isna(domain_name):
                continue

            domain_sections.append(
                {
                    "domain_name": str(domain_name).strip(),
                    "domain_field_name": labels[name_row],
                    "header_row": count,
                }
            )

        # Coded values end at the first blank row or the row before the next domain's name row
        for count, section in enumerate(domain_sections):
            first_row = section["header_row"] + 1
            last_row = first_row

            next_header_row = domain_sections[count + 1]["header_row"] if count + 1 < len(domain_sections) else None

            while last_row < len(labels) and labels[last_row]:

                if next_header_row is not None and last_row + 1 >= next_header_row:
                    break

                last_row += 1

            section["rows"] = (first_row, last_row)

        # Only keep domains assigned to fields, if provided
        if self.field_domains is not None:
            field_domains = {str(x).strip().upper() for x in self.field_domains if x}

            for section in domain_sections:

                if section["domain_name"].upper() not in field_domains:
                    print(f"\tSkipping '{section['domain_name']}' ({section['domain_field_name']}) - "
                          f"not assigned to a field.")

            domain_sections = [x for x in domain_sections if x["domain_name"].upper() in field_domains]

        domain_names = [x["domain_name"] for x in domain_sections]

        # Check that no spaces are in domain - make sure SDSF is filled out correctly
        bad_domain_names = [x for x in domain_names if x.count(" ") > 0]

        if bad_domain_names:
            error_message = f"\n\tDomain filled out incorrectly. " \
                            f"Double check domain names, '{', '.join(bad_domain_names)}' and " \
                            f"ensure no spaces are present."
            raise SpatialDataSubmissionFormError(error_message)

        for section in domain_sections:
            header_row = section["header_row"]
            first_row, last_row = section["rows"]

            # Header row is "Code" / "Description"
            columns = [labels[header_row], str(self.domain_df.iloc[header_row, 0]).strip()]

            domain_df = pd.DataFrame(
                {
                    columns[0]: list(self.domain_df.index[first_row:last_row]),
                    columns[1]: list(self.domain_df.iloc[first_row:last_row, 0]),
                }
            )

            domain_df.dropna(inplace=True)

            domain_df = domain_df.apply(lambda col: col.map(lambda x: x.strip() if isinstance(x, str) else x))

            # Remove any domain dataframes with empty rows
            if not domain_df.empty:
                domain_dataframes[section["domain_name"]] = domain_df

        return domain_names, domain_dataframes
