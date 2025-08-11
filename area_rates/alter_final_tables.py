import os

import arcpy

import pandas as pd

from datetime import datetime

TAX_YEAR = 2024  # TODO: Update me


def rows_from_template(excel_template):
    # TODO: Function not used?

    print(f"\nExtracting rows from {excel_template}...")

    df = pd.read_excel(excel_template)
    df = df.astype({"AAN": str, "PID": str})

    df["AAN"] = df["AAN"].str.zfill(8)
    df["PID"] = df["PID"].str.zfill(8)

    df["AREA_RATE"] = "M052"
    df["TAX_YEAR"] = TAX_YEAR

    print(df.head())
    rows = list(df.itertuples(index=False, name=None))
    return rows


def add_to_feature(add_table, sde_table):
    print(f"Importing rows from {add_table} to {sde_table}...")

    table_rows = [row for row in arcpy.da.SearchCursor(add_table, ["PID", "ACCTNO", "ARCODE"])]
    tax_year = datetime.now().year
    updated = datetime.now()

    # Append rows to SDE Area_Rates_PID_AAN
    with arcpy.da.InsertCursor(sde_table, ["PID", "AAN", "AREARATE_CODE", "TAXYEAR", "UPDATED"]) as cursor:
        for row in table_rows:
            add_row = [x for x in row] + [tax_year, updated]  # Set Updated Date to now
            cursor.insertRow(add_row)

    del cursor


def update_sde_aggregate_table(sde_workspace, final_tax_tables):
    aggregate_final_table = os.path.join(sde_workspace, "Area_Rates_PID_AAN")

    print(f"\nUpdating SDE aggregate table, '{aggregate_final_table}'")

    print(f"Truncating {aggregate_final_table}...")
    arcpy.TruncateTable_management(aggregate_final_table)

    # Append table data from each table
    for table in final_tax_tables:
        add_to_feature(table, aggregate_final_table)

    return aggregate_final_table


def update_service(service_gdb, sde_table):
    print(f"\nUpdating service from {service_gdb}...")

    service_table = os.path.join(service_gdb, "Area_Rates_PID_AAN")

    print("Truncating service gdb table...")
    arcpy.TruncateTable_management(service_table)

    # Append rows
    print("Appending to table...")
    arcpy.Append_management(sde_table, service_table, "NO_TEST")
    print(arcpy.GetMessages())


def copy_previous_year_service_table():
    pass


if __name__ == "__main__":
    # TODO: Add logging

    feature = "SDEADM.Area_Rates_PID_AAN"

    # data = rows_from_template("m052_adds.xlsx")

    DEV_GDB = r"\\msfs06\GISApp\AGS_Dev\fgdbs\web_RO.gdb"
    QA_GDB = r"\\msfs06\GISApp\AGS_QA\fgdbs\web_RO.gdb"
    PROD_GDB = r"\\msfs06\GISApp\AGS_Prod\fgdbs\web_RO.gdb"

    DEV_SDE = r"E:\HRM\Scripts\SDE\SQL\dev_RW_sdeadm.sde"
    QA_SDE = r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde"
    PROD_SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"

    for sde_workspace, gdb_service_workspace in [
        # (DEV_SDE, DEV_GDB),
        (QA_SDE, QA_GDB),
        # (PROD_SDE, PROD_GDB),
    ]:

        print(datetime.now())

        input(f"Is tax year, {TAX_YEAR}, correct?")

        print(f"\nSDE Workspace: {sde_workspace}\n\tGDB Service Workspace: {gdb_service_workspace}")

        # Remove any AAN in M050 that are already in M052

        skip_tables = [
            'AR_REGTRANS_FINAL_SAP',

            'AR_FIRE_REDUCED_RATE_FINAL_SAP',
            'AR_FIRE_WORSHIP_EXPT_FINAL_SAP',

            'AR_TAXDES_MAX_FINAL_SAP',
            'AR_TAXDES_PRE_FINAL_SAP'
        ]

        with arcpy.EnvManager(workspace=sde_workspace):

            final_tables = sorted(
                [x for x in arcpy.ListTables("*_FINAL_SAP") if x.upper().split("SDEADM.")[1] not in skip_tables]
            )

            final_sde_table = update_sde_aggregate_table(
                sde_workspace=sde_workspace,
                final_tax_tables=final_tables
            )

            if gdb_service_workspace:
                update_service(
                    service_gdb=gdb_service_workspace,
                    sde_table=final_sde_table
                )

        # STATISTICS
        # https://gisapp-int-qa.halifax.ca/hrm/rest/services/Area_Rates/Area_Rate_Overlay_Result/MapServer/1/query?where=1%3D1&text=&objectIds=&time=&timeRelation=esriTimeRelationOverlaps&geometry=&geometryType=esriGeometryEnvelope&inSR=&spatialRel=esriSpatialRelIntersects&distance=&units=esriSRUnit_Foot&relationParam=&outFields=*&returnGeometry=false&returnTrueCurves=false&maxAllowableOffset=&geometryPrecision=&outSR=&havingClause=&returnIdsOnly=false&returnCountOnly=false&orderByFields=AREARATE_CODE&groupByFieldsForStatistics=AREARATE_CODE&outStatistics=%5B%7B%0D%0A++++%22statisticType%22%3A+%22count%22%2C%0D%0A++++%22onStatisticField%22%3A+%22AREARATE_CODE%22%2C+%0D%0A++++%22outStatisticFieldName%22%3A+%22Count%22%0D%0A%7D%5D&returnZ=false&returnM=false&gdbVersion=&historicMoment=&returnDistinctValues=false&resultOffset=&resultRecordCount=&returnExtentOnly=false&sqlFormat=none&datumTransformation=&parameterValues=&rangeValues=&quantizationParameters=&featureEncoding=esriDefault&f=html

        print(f"\n{datetime.now()}")
