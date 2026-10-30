# Validation and error checks

The hand-labeled reference is separate from the radar-only Otsu algorithm. All 30 chips are evaluated without supervised fitting; this is an exploratory event benchmark, not an official train/test leaderboard comparison or proof of transfer to another region.

Checks executed by the workflow:

- Published GCS MD5 verified on every downloaded raster; SHA-256 manifest retained.
- CRS, pixel dimensions, grid alignment, band counts, and reference/JRC class codes checked before analysis.
- Raster masks and finite-value screening applied; hand-label −1 omitted from all accuracy denominators.
- Confusion counts reconciled against evaluated pixel counts.
- Area computed geodesically in EPSG:4326, not from an assumed 10 m square.
- Whole-chip bootstrap and threshold perturbations expose sampling and threshold sensitivity.
- Per-chip metrics and spatial false-positive / false-negative rasters expose failures hidden by pooled scores.

Metric definitions: precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN), IoU = TP/(TP+FP+FN), accuracy = (TP+TN)/N. Undefined denominators return null. Confusion matrix rows are reference and columns are prediction.

See `RESULTS.md` for observed metrics and `outputs/metrics.json` for machine-readable checks. Tests use hand-computed confusion counts, nodata exclusions, and a bimodal threshold case; they do not substitute for reference-data assessment.

## What remains uncertain

- Hand annotations are not field-survey truth. The one-day optical/radar difference, clouds, and ambiguous boundaries limit interpretation.
- Pixels are spatially dependent. Bootstrap intervals are conditional on these chips, and do not represent uncertainty in label correctness or national flood area.
- Permanent-water subtraction does not establish new flooding. Seasonal water and JRC errors may be included; flooded vegetation and urban flooding may be missed.
- Flood exposure and damage are unassessed. Before an operational release, acquire a pre-event same-orbit radar stack, terrain masking, independent new-flood labels, and infrastructure data with documented dates.
