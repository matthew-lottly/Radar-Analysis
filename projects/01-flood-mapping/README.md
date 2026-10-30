# 01 · Flood-event mapping and accuracy audit

A reproducible Sentinel-1 baseline for the **17 September 2019 Spain event**, using all 30 Spain hand-labeled Sen1Floods11 chips.

Start with the [geographic holdout assessment](HOLDOUT.md): a calibrated dual-polarization method evaluated on spatially separated chips.

![Geographic holdout maps](outputs/holdout/heldout_mapping.png)

Read [results and maps](RESULTS.md), [methods and run instructions](METHODS.md), and [validation and limitations](VALIDATION.md).

![Water detection and spatial errors](outputs/mapping_and_errors.png)

![Accuracy and sensitivity](outputs/accuracy_dashboard.png)

The validated output is **event-time surface water**. A separate potential-flood layer excludes JRC permanent water but is not validated as new inundation. This release covers sampled chips, not the entire flood, and does not claim flood depth, damage, or infrastructure exposure.
