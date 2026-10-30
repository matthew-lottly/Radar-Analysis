# Methods

## Study design and inputs

Bounding box: longitude −96 to −95.3°, latitude 29.45 to 30.15°. Requested radar frame: OPERA **08882**, VV, **ascending**. Analysis window: **2019-01-01 through 2024-12-31**. GNSS archive support ends earlier at some stations; each comparison reports its actual shared months.

Eight fixed GNSS sites were selected before radar retrieval: ALEF, ADKS, AULT, CFHS, CFJV, CMFB, CSTE, DMFB. Eight power-plant sample sites were selected by descending EIA `Total_MW` within the box, with Plant_Code as a tie-breaker. All selections and exclusions remain visible. This is a small, nonrandom screening sample, not a citywide inventory of deformation.

Infrastructure context contains 58 inventory points with **Period 202502**, from an EIA-attributed ArcGIS feature service. A February 2025 inventory does not establish plant presence throughout 2019–2024. Capacity is used for sample selection only; plant boundaries, asset condition, and tower/tank locations are not known from these facility points.

The GNSS inputs are University of Nevada, Reno tenv3 observations preserved in the **OPERA public calibration/validation archive**. This provenance is distinct from a new retrieval of the latest NGL solution. Raw-source SHA-256 hashes and requests are retained in `source_manifest.json`; normalized input snapshot hashes are in `inputs_snapshot_sha256.json`.

## OPERA time series

1. Read only actual `.nc` product rows; the public point API also returns statistical summary rows that are discarded.
2. Retain source filenames, reference and secondary dates, source pixel-center coordinates, reported masks, and displacement values. Exclude masked and nonfinite values. Deduplicate identical date pairs by latest lexicographic product name.
3. Reconstruct cumulative displacement from edges `d(secondary) − d(reference)` using a sparse incidence matrix and least squares. Anchor the earliest date of the largest connected component to zero. Disconnected components are logged and never concatenated. Current inputs use a single reference date, so there are no independent closure loops; zero graph residual is **not evidence of physical accuracy**.
4. Check query-to-source-pixel offsets in UTM zone 15N, EPSG:32615, against the half diagonal of a 30 m grid cell (<22 m). Check archived GNSS median coordinates against rounded catalog coordinates (<15 m). No masked-pixel fallback or relocation is used.
5. Fit only observations inside 2019–2024. Require at least 24 valid epochs and at least 3 years of temporal span. One of the eight requested power-plant locations fails the epoch-count gate and is excluded, without replacement.

**Observable:** short-wavelength line-of-sight displacement in meters, converted to millimeters for fitting. Positive is toward satellite. The service field is spatially filtered; neither its trend nor its sign uniquely determines vertical subsidence. The source product is sampled at a facility/station coordinate, not over a structure footprint. Fine-scale building or soil behavior may differ from the returned pixel aggregate.

## Trends and formal uncertainty

The design matrix contains intercept, linear time in Julian years (365.25 days), and annual plus semiannual sine/cosine terms. Ordinary least squares fits the mean model. Newey–West/HAC covariance with lag 6 accounts approximately for serial residual dependence; alternative lags 3 and 12 are reported for radar. Lags count retained observations, not fixed elapsed days; irregular sampling and long-memory noise remain limitations. Formal 95% bars use ±1.96 HAC standard errors and are approximate asymptotic intervals, **not complete displacement uncertainty**.

Early/late three-year trends are attempted with the same minimum three-year span. If cadence leaves either half shorter than the gate, its estimate is null rather than silently reducing the gate. No outlier removal is performed on accepted radar epochs. Neither model-fit residuals nor graph residuals are an external accuracy assessment.

## GNSS processing

- Read tenv3 full local coordinates as integer origins plus fractional ENU components. Require finite ENU and positive formal coordinate errors; discard daily up uncertainty >30 mm. Verify the reference meridian is constant.
- Reduce daily coordinates to monthly medians, requiring at least 15 accepted days per month. Do not scale uncertainty by square-root sample size, because daily solutions are correlated.
- Inspect the NGL step metadata snapshot for selected sites and study dates. Omit months containing documented steps and fit eligible step indicators more than six months from each series endpoint. No matching documented steps were found in the acquired snapshot; that does not prove the absence of unmodeled offsets.
- Fit ENU trends using the same seasonal model and HAC lag 6 on monthly observations. Individual station slopes describe their actual supported dates, recorded in CSV.

## Geometry and GNSS comparison

Precise per-pixel STATIC look vectors were not available through the public point API. We therefore evaluate **scenarios**, not measured geometry: incidence 30/35/40/45° and heading −18/−13/−8° (clockwise from north), with 35°/−13° used as a nominal illustration. They bracket plausible ascending right-looking configurations but are not an exhaustive geometry error bound for this frame.

For ground-to-satellite unit vector `l = (−sin(i)cos(h), sin(i)sin(h), cos(i))`, projected GNSS motion is `l_E E + l_N N + l_U U`, with positive LOS toward satellite. A vertical-only interpretation would incur horizontal leakage `(l_E E + l_N N)/l_U`. Sensitivity tables expose that effect using **differential** GNSS velocities relative to ALEF, removing a common regional translation approximately; this is not a plate-motion model.

For each station pair, radar and GNSS are compared on the **identical available calendar months**. Radar epochs are monthly-median reduced and differenced from ALEF; GNSS monthly ENU is differenced from ALEF and projected. Both trends use the same calendar-month timestamps. No extrapolation across missing months is used, and no GNSS-derived correction is fitted to radar.

The spatial operators still differ: OPERA is high-pass filtered, GNSS is not. Accordingly, RMS/mean differences are labeled **conditional compatibility diagnostics**. They are not independent accuracy metrics, and their seven residuals share reference-station errors. No mission requirement pass/fail is claimed.

## Reproducibility

`analyze.py` consumes committed input tables. `acquire.py` and `prepare.py` document how the public services produced them, but upstream URLs can change. Source checksums detect changed content; they do not authenticate the scientific truth of that content. Raw GNSS/OPERA response caches are ignored by git. Scientific values in the frozen tables are not synthetic. `environment-used.txt` records versions used for this execution.
