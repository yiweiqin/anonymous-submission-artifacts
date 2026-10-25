You are an Industrial Engineer supporting the Brightland Processing Center.

Use `/root/process_capability_data.xlsx` (3 sheets: `Task Duration`, `Failure Rate`, `System Errors`) to produce a deterministic process capability and stability assessment.

Create **both** files:

1. `/root/process_capability_report.json`
2. `/root/process_capability_brief.md`

## Required Analysis Rules

Use these exact formulas:

- Mean: arithmetic average
- Sample standard deviation: denominator `n-1`
- Coefficient of variation (CV): `sample_std / mean`
- Failure-rate point value: `Failures / Units processed` (proportion)
- Failure overall rate percent: `100 * sum(Failures) / sum(Units processed)`
- Wilson 95% CI for overall failure rate with:
  - `z = 1.959963984540054`
  - `denom = 1 + z^2 / n`
  - `center = (p + z^2/(2n)) / denom`
  - `half = z * sqrt((p*(1-p) + z^2/(4n))/n) / denom`
- CI bounds in percent: `100 * (center +/- half)`
  - where `p = sum(Failures)/sum(Units processed)` and `n = sum(Units processed)`
- Trend test for each process series:
  - Fit linear regression with `x = 1..N`
  - Compute slope and t-statistic for slope
  - Stability rule: `Stable` iff `abs(t_stat) < 2.0`, else `Unstable`

Series for trend test:

- Task Duration: `Process Duration (min)`
- Failure Rate: per-point failure proportions (`Failures / Units processed`)
- System Errors: `Error Rate`

Variability ranking must compare CV values of:

- Task Duration series
- Failure-rate per-point series
- System Errors `Error Rate` series

## Required JSON Schema

`/root/process_capability_report.json` must contain:

- `task_duration`
- `failure_rate`
- `system_errors`
- `variability_ranking` (sorted highest CV to lowest)
- `highest_variability_process`
- `highest_risk_statement`
- `extended_analysis`
- `monitoring_plan`

### Additional JSON constraints

- `highest_variability_process` must be the top-ranked process by CV.
- `highest_risk_statement` must contain this exact sentence:
  - `System Errors is the highest-risk process.`
- `failure_rate` must include:
  - `uses_varying_denominators` (boolean)
  - `target_rate_pct` set to `1.0`
  - `capability_vs_target` (`Capable` or `Not Capable`)
- `monitoring_plan` must include these keys:
  - `process_to_be_monitored`
  - `inputs`
  - `outputs`
  - `key_performance_indicators`
  - `frequency_of_monitoring`
  - `observation_format`
  - `roles`
  - `reporting_format`
  - `corrective_action_process`
  - `benchmarks`
  - `prioritized_actions`
  - `checklist`
  - `momentum_plan_30_60_90`
  - `project_codename`
- `checklist` must have 5-9 items.

## Required Markdown Brief

`/root/process_capability_brief.md` must include these section headings:

- `Summary of Findings`
- `Most Significant Risks`
- `Prioritized Corrective Actions`
- `Monitoring Plan`

Inside `Monitoring Plan`, include these subsection headings:

- `Process to be Monitored`
- `Inputs`
- `Outputs`
- `Key Performance Indicators (KPIs)`
- `Frequency of Monitoring`
- `Observation Format`
- `Roles`
- `Reporting Format`
- `Corrective Action Process`
- `Benchmarks`

The markdown brief must also include:

- The exact sentence: `System Errors is the highest-risk process.`
- A project codename line
- 30/60/90-day momentum milestones

## Output contract clarification (2026-10-13)

Use these exact JSON field names and nesting for the analyses already requested; compute values from the supplied data using the stated formulas:

- `Top-level JSON`: `extended_analysis`, `failure_rate`, `highest_risk_statement`, `highest_variability_process`, `monitoring_plan`, `system_errors`, `task_duration`, `variability_ranking`
- `extended_analysis`: `capability_evaluation`, `priority_reason`, `process`, `stability_assessment`, `time_trend_review`
- `extended_analysis.time_trend_review`: `direction`
- `failure_rate`: `capability_vs_target`, `overall_rate_pct`, `point_rate_cv`, `points`, `stability`, `target_rate_pct`, `total_failures`, `total_units`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`, `uses_varying_denominators`, `wilson_95_ci_pct`
- `monitoring_plan`: `benchmarks`, `checklist`, `corrective_action_process`, `frequency_of_monitoring`, `inputs`, `key_performance_indicators`, `momentum_plan_30_60_90`, `observation_format`, `outputs`, `prioritized_actions`, `process_to_be_monitored`, `project_codename`, `reporting_format`, `roles`
- `monitoring_plan.momentum_plan_30_60_90`: `day_30`, `day_60`, `day_90`
- `system_errors`: `cv`, `mean_error_rate`, `rows`, `sample_std_error_rate`, `stability`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`
- `task_duration`: `cv`, `mean_min`, `n`, `sample_std_min`, `stability`, `stability_method`, `trend_direction`, `trend_slope_per_index`, `trend_t_stat`

Each variability_ranking entry must contain `process` (the corresponding JSON process key) and numeric `cv`; sort by decreasing CV. Use `increasing`, `decreasing`, or `flat` for trend direction, and `Stable` or `Unstable` for stability. Fields ending in `_pct` and confidence-interval bounds are percentages; calculate point-rate CV and trends from proportions. Mean and sample-standard-deviation fields retain the units indicated by their field names. Narrative assessment and priority fields must explain the evidence in complete sentences, not just a label.
