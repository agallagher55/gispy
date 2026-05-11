# Speed Limit Neighbourhood Dynamic Segmentation

## Purpose

Create a separate segmented representation that combines these LRS events on `LRSN_Route`:

- `SDEADM.E_StreetClass`
- `SDEADM.E_SpeedLimit`
- `SDEADM.E_SpeedLimit_Neighborhood` (or `SDEADM.E_SpeedLimit_Neighbourhood` if that is the name in the target geodatabase)

The output supports a speed-limit neighbourhood review layer with the fields shown in the requested model:

| Output field | Source |
| --- | --- |
| `ROUTE_ID` | `LRSN_Route.ROUTEID` via overlay output `ROUTEID` |
| `STR_NAME` | `LRSN_Route.STR_NAME` |
| `FULL_NAME` | `LRSN_Route.ROUTENAME` |
| `STR_CLASS` | `E_StreetClass.ST_CLASS` |
| `SPEED` | `E_SpeedLimit.SPEED` |
| `REVIEW_STAT` | `E_SpeedLimit_Neighborhood.REVIEW_STAT` |
| `DATE_EFFECTIVE` | `E_SpeedLimit_Neighborhood.DATE_EFFECTIVE` |
| `SHAPE` | Dynamic segmentation geometry from `OverlayEvents` |

## Implementation

`LRS/LRS_updates.py` now has speed-limit-specific methods on `DynSegFeature`:

1. `update_speed_limit_neighbourhood_segmentation()`
   - Runs `arcpy.locref.OverlayEvents` against `LRSN_Route`.
   - Uses only `E_StreetClass`, `E_SpeedLimit`, and `E_SpeedLimit_Neighborhood` by default.
   - Creates `TRNLRS_segmented_speed_limit_events` in the configured SDE workspace.
   - Grants `PUBLIC` view access to the segmented feature.

2. `update_speed_limit_neighbourhood(out_feature, segmented_feature_name=...)`
   - Builds a query layer from the segmented feature.
   - Filters to active rows with `e.TO_DATE IS NULL`.
   - Maps overlay fields into the target output schema.
   - Calls `append_feature()` to truncate and load the target feature class.

Example usage:

```python
dyn_seg = DynSegFeature(sde_workspace=SDEADM_RW)

# Create or refresh the event-specific segmented representation.
dyn_seg.update_speed_limit_neighbourhood_segmentation()

# Load a publishable output feature class that already has the expected schema.
dyn_seg.update_speed_limit_neighbourhood(
    out_feature=rf"{SDEADM_RW}\SDEADM.SpeedLimit_Neighbourhood_VW"
)
```

If the event class in the database is named with Canadian spelling, pass the alternate event name:

```python
dyn_seg.update_speed_limit_neighbourhood_segmentation(
    neighbourhood_event_name="SDEADM.E_SpeedLimit_Neighbourhood"
)
```

## Should `E_SpeedLimit` and `E_SpeedLimit_Neighbourhood` be added to `self.event_tables`?

No, not for this requirement. `self.event_tables` is the event list used by `update_dynamic_segmentation()` to create the primary `TRNLRS_segmented_street_events` feature that feeds `TRNLRS_TRN_street_VW`, retired streets, and street lanes.

The speed-limit neighbourhood output should be generated as a separate overlay because it has a different purpose and a smaller output schema. Keeping it separate avoids changing the segmentation grain and schema of the existing street-view pipeline.

## Impact on `TRNLRS_trn_street_vw`

Adding `E_SpeedLimit` and `E_SpeedLimit_Neighbourhood` to the main `self.event_tables` list would impact the creation of `TRNLRS_trn_street_vw` because `OverlayEvents` splits output geometry at every event boundary from every input event table. Speed-limit and neighbourhood-review events can introduce additional breakpoints that do not align with address range or street-class segments.

Likely impacts of adding them to the main overlay include:

- More rows in `TRNLRS_segmented_street_events` and therefore potentially more rows feeding `TRNLRS_TRN_street_VW`.
- Existing QA checks may report new duplicate `FDMID` values or short segments because the same street segment can be split by speed-limit boundaries.
- Downstream consumers expecting one row per existing street segment may see changed geometry lengths or duplicate street attributes.
- The main street view SQL would need explicit field handling for `SPEED`, `REVIEW_STAT`, and `DATE_EFFECTIVE`; otherwise the fields may exist only in the intermediate feature and not in the published street outputs.

For those reasons, the speed-limit neighbourhood overlay should remain independent unless the business requirement is to permanently change the segmentation rules for the primary street view.

## Validation checklist

Before running in production:

1. Confirm the actual event class spelling in SDE: `E_SpeedLimit_Neighborhood` vs. `E_SpeedLimit_Neighbourhood`.
2. Confirm `E_StreetClass` exposes `ST_CLASS`; the output aliases it to `STR_CLASS`.
3. Confirm the target publishable feature class exists and includes `ROUTE_ID`, `STR_NAME`, `FULL_NAME`, `STR_CLASS`, `SPEED`, `REVIEW_STAT`, `DATE_EFFECTIVE`, and `SHAPE`.
4. Run the segmentation in a test workspace first and compare row counts and geometry lengths against the source events.
5. Do not add the speed-limit events to the primary `self.event_tables` unless the `TRNLRS_TRN_street_VW` segmentation contract is intentionally being changed.
