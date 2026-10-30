# Completing the full-band subsidence study

The public-data pilot is executed. The requested absolute subsidence and independent radar accuracy assessment remain gated by additional inputs; they are not marked complete.

## Required input access

Full OPERA DISP-S1 NetCDF and matched DISP-S1-STATIC geometry are available from ASF with a free NASA Earthdata login. Standard downloads were unavailable without authentication in this session. The older anonymous OPERA product directory now retains GNSS archives but no displacement NetCDF stack. No credentials were requested in code, stored in this repository, or inferred from local files.

To continue, use an authenticated local/Colab session to obtain **spatial subsets** for frame 08882 covering the selected sites and 2019–2024, including the necessary reference-date links. Preserve the actual primary observation units and pixel geometry. Avoid downloading a full multi-year frame unnecessarily; OPERA's public tutorial describes `opera-utils disp-s1-download --frame-id ... --bbox ...` for subsetting. Authenticate using the official Earthdata/ASF workflow on your own device; never put a password or token in a GitHub file or chat message.

Relevant official starting points:

- [ASF Earthdata collection](https://www.earthdata.nasa.gov/data/catalog/asf-opera-l3-disp-s1-v1-1)
- [OPERA subsidence tutorial and subset-download instructions](https://github.com/OPERA-Cal-Val/OPERA_Applications/tree/main/DISP/Subsidence)
- [OPERA full calibration/validation workflow](https://github.com/OPERA-Cal-Val/calval-DISP)

## Scientific completion gates

1. Obtain full-band displacement, per-epoch recommended masks/quality layers, corrections metadata, and measured ground-to-satellite ENU vectors from matching STATIC products.
2. Verify CRS/grid/units/version alignment; reconstruct reference-date links without joining disconnected networks or mixing spatial filters.
3. Evaluate source quality/coherence and spatial reference stability using actual arrays; retain exclusions and sensitivity cases.
4. Match GNSS epochs, reference station, reference frame, seasonal model, and spatial filtering. Compare ENU projected into measured LOS rather than assuming vertical motion.
5. Reserve independent stations for assessment, report station-level bias/MAE/RMSE with uncertainty, and account for common-reference and spatial correlations. Do not import validation scores from other studies.
6. Only estimate vertical motion if a second useful orbit or justified horizontal-motion constraints support it. Keep LOS and vertical products separately named.
7. Produce continuous displacement/velocity GeoTIFFs and facility-window summaries from measured arrays, with observation counts, uncertainties, geometry sensitivity, and per-site support. Do not infer plant condition, cause, or future damage from motion alone.

The existing graph, trend, projection, and output tests form reusable components; they do not substitute for running these full-data gates.
