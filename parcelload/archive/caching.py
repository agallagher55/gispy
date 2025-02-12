import arcpy

"""
APP-P21
- Parcel Polygon copied to rE:\\temp\\Parcel Load\\October\\results\\ since HRM\server_accoun that was used to open Pro
    with isn't mapped to T:
- Parcel Polygon WGS84 output to E: location as well (never copied back to T:)
"""

arcpy.management.TruncateTable(r"E:\HRM\Data\Cache_Data\Halifax_Basemap_Data_NAD83.gdb\LND_parcel_polygon")
arcpy.management.Append(r"'E:\temp\Parcel Load\October\results\Parcel_Polygon.shp'", r"E:\HRM\Data\Cache_Data\Halifax_Basemap_Data_NAD83.gdb\LND_parcel_polygon", "NO_TEST", r'PID "PID" true true false 8 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,PID,0,12;FCODE "FCODE" true true false 12 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,FCODE,0,12;SOURCE "SOURCE" true true false 12 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,SOURCE,0,12;SACC "SACC" true true false 2 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,SACC,0,2;SDATE "SDATE" true true false 8 Date 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,SDATE,-1,-1;OPERATOR "OPERATOR" true true false 8 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon.shp,OPERATOR,0,8', '', '')
arcpy.management.Project(
    r"E:\temp\Parcel Load\October\results\Parcel_Polygon.shp",
    r"E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84",
    'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Mercator_Auxiliary_Sphere"],PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]',
    "'NAD83_CSRS_1997_to_NAD83_CSRS_2010 + NAD_1983_CSRS_To_WGS_1984_2'",
    'PROJCS["NAD_1983_CSRS_2010_MTM_5_Nova_Scotia",GEOGCS["GCS_North_American_1983_CSRS_2010",DATUM["D_North_American_1983_CSRS",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",25500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",-64.5],PARAMETER["Scale_Factor",0.9999],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]',
    "NO_PRESERVE_SHAPE",
    None,
    "NO_VERTICAL"
)

arcpy.management.TruncateTable(r"E:\HRM\Data\Cache_Data\AGOL_Halifax_Basemap_Data_WGS84.gdb\LND_parcel_polygon")
arcpy.management.Append(r"'E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp'", r"E:\HRM\Data\Cache_Data\AGOL_Halifax_Basemap_Data_WGS84.gdb\LND_parcel_polygon", "NO_TEST", r'PID "PID" true true false 8 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,PID,0,12;FCODE "FCODE" true true false 12 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,FCODE,0,12;SOURCE "SOURCE" true true false 12 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,SOURCE,0,12;SACC "SACC" true true false 2 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,SACC,0,2;SDATE "SDATE" true true false 8 Date 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,SDATE,-1,-1;OPERATOR "OPERATOR" true true false 8 Text 0 0,First,#,E:\temp\Parcel Load\October\results\Parcel_Polygon_WGS84.shp,OPERATOR,0,8', '', '')

