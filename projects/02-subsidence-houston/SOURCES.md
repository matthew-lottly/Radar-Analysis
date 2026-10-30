# Data sources and attribution

Accessed 29 October 2026 (America/Chicago); source-response hashes are in `source_manifest.json`.

1. **NASA OPERA / ASF DISP-S1**, modified Copernicus Sentinel-1 data. Public ASF point API used by the Displacement Portal: `https://d2qmcvu7qty7vn.cloudfront.net/timeseries`. Requested frame 08882, VV, ascending. Exact request bodies and returned product filenames are preserved. This API is a public access interface; reproducibility uses frozen observations because endpoints and results can change.
   - [OPERA DISP product suite](https://www.jpl.nasa.gov/go/opera/products/disp-product-suite/)
   - [ASF displacement documentation](https://docs.asf.alaska.edu/vertex/displacement/)
   - [Filtering FAQ](https://docs.asf.alaska.edu/datasets/disp_faq/)
   - [Usage and point-measurement limitations](https://docs.asf.alaska.edu/datasets/disp_usage/)
   - [Dataset DOI](https://doi.org/10.5067/SNWG/OPL3DISPS1-V1)
   - [ASF portal implementation](https://github.com/asfadmin/Discovery-SearchUI), source examined to identify the public interface. No authenticated archive data were accessed.
2. **Nevada Geodetic Laboratory GNSS**, archived by the OPERA calibration/validation team at `https://opera-pst-rs-pop1.s3.us-west-2.amazonaws.com/products/DISP_S1/GNSS_Calval_archive/F08882/`. Station catalog and original tenv3 URLs are in the manifest. These are archived solutions, not a claim of the newest NGL reference-frame realization.
   - [NGL](https://geodesy.unr.edu/)
   - [OPERA calibration/validation methods](https://github.com/OPERA-Cal-Val/calval-DISP)
   - [NGL step metadata](https://geodesy.unr.edu/NGLStationPages/steps.txt), snapshot inspected for station/date matching.
   - Credit: Blewitt, G., Hammond, W. C., and Kreemer, C. (2018), *Harnessing the GPS data explosion for interdisciplinary science*, Eos, 99. [DOI](https://doi.org/10.1029/2018EO104623).
3. **EIA-attributed power-plant inventory**, `Power_Plants_in_the_US` ArcGIS service, published period 202502. Attributes cite EIA-860, EIA-860M, and EIA-923. This is a hosted EIA-derived snapshot, not a fresh direct extraction of all EIA survey workbooks. Request: bounding-box intersection, all attributes, WGS84 GeoJSON; 58 returned points, no transfer-limit truncation.
   - [Feature-service layer](https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/Power_Plants_in_the_US/FeatureServer/0)
   - [EIA plant-coordinate documentation](https://www.eia.gov/tools/faqs/faq.php?id=567&t=3)
   - [EIA-860](https://www.eia.gov/electricity/data/eia860/)

Derived figures and analysis code are newly produced here. Retain NASA/OPERA, Copernicus Sentinel, NGL/UNR, and EIA/service attribution when reusing observations or figures. See upstream terms for source-specific licensing; this project does not relicense source data. No published paper's figures, rate map, or claimed validation score is reused as this project's result.

4. **U.S. Census TIGERweb cartographic context**, retrieved 29 October 2026: county outlines from `TIGERweb/State_County/MapServer/1` (Texas intersecting the study box) and primary roads from `TIGERweb/Transportation/MapServer/2`. Geometry is generalized at 0.0005° for illustration and clipped visually to map bounds. These present-day background lines are not infrastructure-condition measurements or historical 2019 road coverage. Frozen GeoJSON is included with input checksums.
   - [County service](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1)
   - [Primary roads service](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/2)
