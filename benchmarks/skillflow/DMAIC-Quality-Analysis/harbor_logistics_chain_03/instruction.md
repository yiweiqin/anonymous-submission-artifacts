You are a Supply Chain Analyst supporting Meridian Global Logistics.

Use `/root/logistics_reliability_data.xlsx` (3 sheets: `Delivery Times`, `Damage Rates`, `Order Accuracy`) to produce a deterministic performance and risk assessment.

Create **both** files:

1. `/root/logistics_reliability_report.json`
2. `/root/logistics_reliability_brief.md`

## Required Analysis Rules

Use these exact formulas:

- Mean: arithmetic average
- Sample standard deviation: denominator `n-1`
- Coefficient of variation (CV): `sample_std / mean`
- Damage Rates point value: `Damaged / Shipments` (proportion)
- Damage Rates overall rate percent: `100 * sum(Damaged) / sum(Shipments)`
- Wilson 95% CI for overall damage rates rate with:
  - `z = 1.959963984540054`
  - `denom = 1 + z^2 / n`
  - `center = (p + z^2/(2n)) / denom`
  - `half = z * sqrt((p*(1-p) + z^2/(4n))/n) / denom`
- CI bounds in percent: `100 * (center +/- half)`
  - where `p = sum(Damaged)/sum(Shipments)` and `n = sum(Shipments)`
- Trend test for each process series:
  - Fit linear regression with `x = 1..N`
  - Compute slope and t-statistic for slope
  - Stability rule: `Stable` iff `abs(t_stat) < 2.0`, else `Unstable`

Series for trend test:

- Delivery Times: `Delivery Time (hrs)`
- Damage Rates: per-point proportions (`Damaged / Shipments`)
- Order Accuracy: `Error Rate`

Variability ranking must compare CV values of:

- Delivery Times series
- Damage Rates per-point series
- Order Accuracy `Error Rate` series

## Required JSON Schema

`/root/logistics_reliability_report.json` must contain:

- `delivery_times`
- `damage_rates`
- `order_accuracy`
- `variability_ranking` (sorted highest CV to lowest)
- `highest_variability_process`
- `highest_risk_statement`
- `extended_analysis`
- `variance_diagnostic`
- `action_plan`

### Additional JSON constraints

- `highest_variability_process` must be the top-ranked process by CV.
- `highest_risk_statement` must contain this exact sentence:
  - `Order Accuracy is the highest-risk process.`
- `damage_rates` must include:
  - `uses_varying_denominators` (boolean)
  - `target_rate_pct` set to `1.5`
  - `capability_vs_target` (`Capable` or `Not Capable`)
- `variance_diagnostic` must include these keys:
  - `process_analyzed`
  - `amplification_detected` (boolean)
  - `severity`
  - `pattern_type`
  - `origin_layer`
  - `recommended_intervention`
- `action_plan` must include these keys:
  - `prioritized_actions`
  - `checklist`
  - `project_codename`
  - `momentum_plan_30_60_90`
- `checklist` must have 5-9 items.

## Required Markdown Brief

`/root/logistics_reliability_brief.md` must include these section headings:

- `Summary of Findings`
- `Most Significant Risks`
- `Prioritized Corrective Actions`
- `Variance Diagnostic`
- `Action Plan`

The markdown brief must also include:

- The exact sentence: `Order Accuracy is the highest-risk process.`
- A project codename line
- 30/60/90-day momentum milestones

## Output contract clarification (2026-10-13)

Use these exact JSON field names and nesting for the analyses already requested; compute values from the supplied data using the stated formulas:

- `Top-level JSON`: `action_plan`, `damage_rates`, `delivery_times`, `extended_analysis`, `highest_risk_statement`, `highest_variability_process`, `order_accuracy`, `variability_ranking`, `variance_diagnostic`
- `action_plan`: `checklist`, `momentum_plan_30_60_90`, `prioritized_actions`, `project_codename`
- `action_plan.momentum_plan_30_60_90`: `day_30`, `day_60`, `day_90`
- `damage_rates`: `capability_vs_target`, `overall_rate_pct`, `point_rate_cv`, `points`, `stability`, `target_rate_pct`, `total_damaged`, `total_shipments`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`, `uses_varying_denominators`, `wilson_95_ci_pct`
- `delivery_times`: `cv`, `mean_hrs`, `n`, `sample_std_hrs`, `stability`, `stability_method`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`
- `extended_analysis`: `capability_evaluation`, `priority_reason`, `process`, `stability_assessment`, `time_trend_review`
- `extended_analysis.time_trend_review`: `direction`
- `order_accuracy`: `cv`, `mean_error_rate`, `rows`, `sample_std_error_rate`, `stability`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`
- `variance_diagnostic`: `amplification_detected`, `origin_layer`, `pattern_type`, `process_analyzed`, `recommended_intervention`, `severity`

Each variability_ranking entry must contain `process` (the corresponding JSON process key) and numeric `cv`; sort by decreasing CV. Use `increasing`, `decreasing`, or `flat` for trend direction, and `Stable` or `Unstable` for stability. Fields ending in `_pct` and confidence-interval bounds are percentages; calculate point-rate CV and trends from proportions. Mean and sample-standard-deviation fields retain the units indicated by their field names. Narrative assessment and priority fields must explain the evidence in complete sentences, not just a label.
