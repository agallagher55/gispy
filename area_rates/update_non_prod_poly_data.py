import arcpy
import os

from datetime import datetime

from area_rates.area_rates import AREA_RATE_FEATURES


def update_polygons(rate_boundaries, update_sde, reference_sde):
    print(f"\nUpdating polygons in \n\t'{update_sde}' with data FROM \n\t'{reference_sde}'...")

    # TODO: Add parcels, LINNS_PIDRELATE, LINNS_PIDAANTAX to list of polygons to update
    update_features = [
        r"SDEADM.LND_parcels/SDEADM.LND_parcel_polygon",
        r"SDEADM.LINNS_PIDRELATE",
        r"SDEADM.LINNS_PIDAANTAX",
    ] + list(rate_boundaries.keys())

    num_update_features = len(update_features)

    for count, poly in enumerate(update_features, start=1):
        print(f"\n{count}/{num_update_features}) {poly}")

        update_poly = os.path.join(update_sde, poly)
        reference_poly = os.path.join(reference_sde, poly)

        try:
            # Delete rows
            arcpy.DeleteRows_management(update_poly)

            # Append
            arcpy.Append_management(
                reference_poly,
                update_poly,
                "NO_TEST"
            )
            print(arcpy.GetMessages())

        except arcpy.ExecuteError:
            print(arcpy.GetMessages(2))
            continue


if __name__ == "__main__":
    PROD_SDE = r"E:\HRM\Scripts\SDE\SQL\Prod\prod_RW_sdeadm.sde"

    # update_sde = r"E:\HRM\Scripts\SDE\SQL\Dev\dev_RW_sdeadm.sde"
    update_sde = r"E:\HRM\Scripts\SDE\SQL\qa_RW_sdeadm.sde"

    YEAR = datetime.now().year

    update_polygons(
        rate_boundaries=AREA_RATE_FEATURES,
        update_sde=update_sde,
        reference_sde=PROD_SDE
    )

