# Validation and error assessment

## Executed checks

- Preserve source-product names, observation dates, reported masks, source pixel centers, raw-response SHA-256 hashes, and frozen input hashes.
- Exclude API summary rows and masked/nonfinite radar observations; log all data-gate exclusions.
- Verify station coordinates, source-pixel offsets, date ordering, constant GNSS reference meridian, graph connectivity, and solver convergence.
- Require temporal span and sample support before fitting; publish actual GNSS month coverage and common comparison months.
- Reconstruct full GNSS coordinates, screen daily solution errors, inspect documented steps, and preserve missing periods.
- Fit seasonal terms and compare formal covariance under several serial-correlation lags.
- Test LOS vector signs and unit norm, graph reference changes/disconnected segments/cycle inconsistency, seasonal trend recovery, duplicate-date rejection, and output accounting.
- Review all four figures visually before publication.

Results and per-site diagnostics are in `outputs/metrics.json`, `outputs/opera_rates.csv`, `outputs/gnss_rates.csv`, and `outputs/excluded_sites.json`.

## Accuracy status

**Independent, geometry- and filtering-matched radar accuracy is not established.** The available GNSS comparison is deliberately labeled a compatibility diagnostic, because the public radar endpoint exposes a spatially high-pass-filtered field and does not return the matching pixel look vector or full uncertainty arrays. We do not quote the performance reported by other studies as this project's accuracy.

The single-reference graph has no independent cycles, so a near-zero inversion residual is algebraic consistency only. The service-provided mask is used as reported; coherence thresholds and mask-generation internals are not independently checked here. Formal HAC uncertainty excludes spatial-filter effects, atmospheric systematics, unwrapping biases, structure-specific scattering, and source-reference uncertainty.

Known station steps were checked in a later NGL metadata snapshot than the archived position solutions. Lack of a matched metadata entry is not evidence that offsets are absent. No external field inspection or independent plant-specific deformation measurement was available. Infrastructure overlays show spatial context, not structural damage, facility failure, or causal attribution to groundwater/hydrocarbon extraction.

See [NEXT_STEPS.md](NEXT_STEPS.md) for the additional inputs and checks needed to promote this exploratory pilot to a full-band subsidence study.
