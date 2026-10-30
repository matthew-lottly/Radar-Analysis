# Methods and reproducibility

## Data and scope

This first project uses **all 30 Spain hand-labeled chips** in Sen1Floods11 v1.1. Each 512 × 512 chip has two Sentinel-1 GRD bands in dB (VV, VH), a separately produced hand-labeled surface-water reference, and a JRC permanent-water mask. Source event metadata records Sentinel-1 on 2019-09-17, Sentinel-2 on 2019-09-18, descending relative orbit 110. The chips cover portions of southeastern Spain; they are not a wall-to-wall event inventory.

Source: [Cloud to Street / Sen1Floods11](https://github.com/cloudtostreet/Sen1Floods11), pinned documentation commit `b9e460dabe70230111a3c3d36cd0c5ce03606ee9`. Original data: `gs://sen1floods11/v1.1/`. Every raster's immutable GCS generation URL, published MD5, byte size, and locally computed SHA-256 are recorded in `manifest.json`. Raw data are downloaded rather than committed.

Citation: Bonafilia, D., Tellman, B., Anderson, T., and Issenberg, E. (2020). *Sen1Floods11: a georeferenced dataset to train and test deep learning flood algorithms for Sentinel-1*. IEEE/CVF CVPR Workshops, 210–211. [Paper](https://openaccess.thecvf.com/content_CVPRW_2020/html/w11/Bonafilia_Sen1Floods11_A_Georeferenced_Dataset_to_Train_and_Test_Deep_Learning_CVPRW_2020_paper.html).

Retain source attribution and consult upstream data terms before redistribution. Derived results here do not change upstream rights.

## Algorithm

1. Require matching CRS, dimensions, and affine grids within 1e-12 degrees (floating-point serialization tolerance, far below a pixel). Fail on unexpected reference or JRC codes.
2. Exclude raster-masked, nonfinite, or screened-out backscatter (VV or VH outside −50 to +10 dB). This conservative screening is an analysis choice, not a universal sensor-validity rule.
3. Calculate a 256-bin VH histogram over −50 to +10 dB using radar-valid pixels only. Select the threshold maximizing Otsu between-class variance. Classify VH below that threshold as water. Reference labels and the dataset's published `VH_thresh` are not used in classification. No learned model, label tuning, or morphological cleanup is applied.
4. Map **potential flooding** as detected water where JRC equals 0. JRC unknown pixels remain nodata. This is a proxy for nonpermanent water, not independently validated new inundation.
5. Evaluate surface-water predictions on radar-valid pixels where hand labels are 0 or 1. Ignore −1. Store TP, FP, FN, TN, precision, recall, F1, IoU, specificity, overall accuracy, and water prevalence, both per chip and pooled.
6. Perturb each threshold by −2, −1, +1, +2 dB and report all results; do not choose a better threshold using test labels.
7. Resample whole chips 2,000 times with seed 20261029 to estimate percentile intervals. These are exploratory tile-bootstrap intervals; neighboring chips may remain correlated.
8. Compute pixel areas from WGS84 geodesic quadrilaterals. Do not assume geographic pixels have 100 m² area. Sum only sampled footprints and disclose domain differences.

## Run

From the repository root with Python 3.11+:

```bash
python -m pip install -r projects/01-flood-mapping/requirements.txt
python projects/01-flood-mapping/download.py
python projects/01-flood-mapping/analyze.py
python projects/01-flood-mapping/holdout.py
python -m unittest discover -s projects/01-flood-mapping/tests -v
```

`download.py` replays the committed manifest using immutable generation URLs and verifies both MD5 and SHA-256, including cached files. If no manifest exists, it discovers all Spain objects and creates one. The event metadata snapshot is committed as `event_metadata.geojson`.

## Output encodings

| Output | Encoding / interpretation |
|---|---|
| `*_water.tif` | 0 dry, 1 water, 255 nodata; full radar-valid domain |
| `*_potential_flood.tif` | 0 excluded/dry/permanent, 1 water outside permanent mask, 255 radar/JRC unknown |
| `*_error.tif` | 0 true negative, 1 true positive, 2 false positive, 3 false negative, 255 unevaluated |
| `potential_flood.geojson.gz` | WGS84 potential-flood pixel polygons, tagged by chip; no minimum-size removal |
| `per_chip.csv` | Counts, metrics, thresholds, and area accounting per chip |
| `metrics.json` | Pooled metrics, intervals, sensitivity, QA status |

No pixel-level probability, flood depth, flood peak, or damage inference is provided. Infrastructure exposure requires a separately acquired and dated roads/buildings dataset; this release deliberately leaves that quantity unreported.

The calibrated geographic-holdout experiment is documented separately in [HOLDOUT.md](HOLDOUT.md). It does not replace or hide the label-blind baseline. Decompress the GeoJSON with gzip before opening in software that lacks gzip support.
