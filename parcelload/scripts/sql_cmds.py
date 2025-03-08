import arcpy

arcpy.SetLogHistory(False)


def execute_sql(sql_script: str, sde_conn):
    conn = arcpy.ArcSDESQLExecute(sde_conn)

    try:
        print(f"\nExecuting '{sql_script}'")

        # Read sql file to get sql commands
        with open(sql_script, "r") as sfile:
            sql = sfile.read()
            print(sql)

        query_result = conn.execute(sql)

        if query_result:
            print(f"Query result successful: {query_result}")
            return query_result

        else:
            error_message = "Not sure if SQL ran successfully. Check results."

            if error_message:
                print(error_message)

        print("\n\n---------------------------------------------------------------------------------\n\n")

    except Exception as e:
        print(f"ERROR: {e}")


def pid_report(pids, out_file=r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\newparcels1.lst"):

    pid_query = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\pid_query.txt"

    print("\nCreating new PID report...")

    pid_list = [x[0] for x in pids]
    query = "PID IN (" + ', '.join([f"'{x}'" for x in pid_list]) + ")"

    with open(out_file, "w") as writer:
        for row in pid_list:
            writer.write(f"{row}\n")

    with open(pid_query, "w") as query_writer:
        query_writer.write(query)

    print(f"\tNew PID file exported to: '{out_file}'")

    return out_file


if __name__ == "__main__":
    from parcelload.archive.settings_section2 import SDE_RW

    new_pidreport_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\create_newpid_report.sql"  # @create_newpid_report.sql

    update_parcel_line_fcode_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_parcel_line_fcode.sql"
    update_parcel_poly_fcode_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_parcel_poly_fcode.sql"
    update_linnstemp_batch_sql = r"T:\work\giss\tools\Parcel Load\Parcel Load sqls\SQL Server\update_linnstemp_batch.sql"

    new_pids = execute_sql(new_pidreport_sql, SDE_RW)
    pid_report(new_pids)

    execute_sql(update_parcel_line_fcode_sql, SDE_RW)
    execute_sql(update_parcel_poly_fcode_sql, SDE_RW)
    
    input("Update locator")
    # """
    # Rebuild PID_Locator_NAD83
    #     •	Open ArcCatalog on DC1-GIS-APP-P22 as arcgis_server_accoun user.
    #     •	Navigate to E:\HRM\Scripts\Python\Update_Geocoders\geocoders
    #     •	Right click and rebuild PID_Locator_NAD83 locator.
    # """

    execute_sql(update_linnstemp_batch_sql, SDE_RW)





