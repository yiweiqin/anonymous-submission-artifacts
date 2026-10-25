# 附录草稿：开发集 66 题的验收拆分

这份清单只拆已有验收脚本，不新增官方分数。每道 Harbor 题的 reward.txt 仍是整份验收通过为 1，否则为 0。下面的每一条是验收源码里的一处断言。

循环里的断言在一次作答中会按数据行再执行。这里按源码出现一次记一条，并标成“随行重复”，不把行数乘进样本数。

来源是 task-contract-evidence/current 里这 8 个开发家族的 tests。Python 题的实际断言在 test_outputs.py；test.sh 先调用 test_output.py，再由它转去跑这份文件。Inventory 的 8 题在 test_outputs.js，由 node 执行，外层同样收成一个 0 或 1。

## 汇总

| 家族 | 官方题 | 具名测试函数 | 断言处 | 其中在循环内 |
|---|---:|---:|---:|---:|
| Healthcare-Cost-Benefit-Analysis | 9 | 47 | 185 | 45 |
| DMAIC-Quality-Analysis | 9 | 48 | 275 | 34 |
| SEC-13F-Financial-Analysis | 8 | 21 | 45 | 4 |
| Compensation-Scenario-Modeling | 8 | 10 | 163 | 31 |
| Weighted-Risk-Assessment | 8 | 48 | 72 | 16 |
| Embedded-Data-Repair | 8 | 35 | 90 | 3 |
| Inventory-&-Finance-Integration | 8 | 0 | 208 | 148 |
| Operational-Recovery-Planning | 8 | 20 | 338 | 131 |
| 合计 | 66 | 229 | 1376 | 412 |

Inventory 的 8 题没有 pytest 测试函数，208 条断言都写在各自的 main 里，所以具名测试函数按 0 计。其余 58 题共有 229 个 test_* 函数。

## 逐题断言

## Healthcare-Cost-Benefit-Analysis

### harbor_cyclemargin_30v90

断言 19 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_cyclemargin_30v90/tests/test_outputs.py

load_output

1. 第 81 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 86 行：OUTPUT_JSON.exists()
3. 第 87 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 92 行：set(data.keys()) == {'assumptions', 'therapies', 'totals', 'recommendation'}
5. 第 93 行：data['assumptions'] == {'patients_per_therapy': PATIENTS, 'fills_per_year_30_day': FILLS_30, 'fills_per_year_90_day': FILLS_90, 'doses_per_fill_30_day': DOSES_30, 'doses_per_fill_9
test_rows_and_order

6. 第 106 行：[r['therapy'] for r in data['therapies']] == [r['therapy'] for r in expected_rows]
test_totals_and_decision

7. 第 122 行：close(totals['total_annual_margin_30_day_usd'], total_30)
8. 第 123 行：close(totals['total_annual_margin_90_day_usd'], total_90)
9. 第 124 行：close(totals['total_annual_margin_difference_90_minus_30_usd'], total_diff)
10. 第 125 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 126 行：data['recommendation']['decision'] == decision
12. 第 127 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 134 行：4 <= len(lines) <= 8
14. 第 137 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 108 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 139 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 111 行：actual[key] == expected_value；随行重复
18. 第 113 行：actual[key] == expected_value；随行重复
19. 第 115 行：close(actual[key], expected_value)；随行重复

### harbor_diagpanel_14v28

断言 21 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_diagpanel_14v28/tests/test_outputs.py

load_output

1. 第 132 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 137 行：OUTPUT_JSON.exists()
3. 第 138 行：OUTPUT_SUMMARY.exists()
test_template_preservation_and_schema

4. 第 144 行：data['metadata'] == metadata
5. 第 145 行：data['audit_notes'] == audit_notes
6. 第 146 行：set(data['analysis'].keys()) == {'assumptions', 'panels', 'totals', 'recommendation'}
7. 第 147 行：data['analysis']['assumptions'] == {'runs_per_year_14_day': RUNS_14, 'runs_per_year_28_day': RUNS_28, 'switch_threshold_usd': THRESHOLD, 'override_rule': 'highest numeric approved 
test_rows_and_order

8. 第 160 行：[row['panel_code'] for row in data['analysis']['panels']] == [row['panel_code'] for row in expected_rows]
test_totals_and_decision

9. 第 176 行：close(totals['total_annual_margin_14_day_usd'], total_14)
10. 第 177 行：close(totals['total_annual_margin_28_day_usd'], total_28)
11. 第 178 行：close(totals['total_annual_margin_difference_28_minus_14_usd'], total_diff)
12. 第 179 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
13. 第 180 行：data['analysis']['recommendation']['decision'] == decision
14. 第 181 行：data['analysis']['recommendation']['justification'].strip()
test_summary_requirements

15. 第 188 行：4 <= len(lines) <= 8
16. 第 191 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

17. 第 162 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

18. 第 193 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

19. 第 165 行：actual[key] == expected_value；随行重复
20. 第 167 行：actual[key] == expected_value；随行重复
21. 第 169 行：close(actual[key], expected_value)；随行重复

### harbor_gdpval_42

断言 31 处，其中 6 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_gdpval_42/tests/test_outputs.py

load_output

1. 第 97 行：f'Missing output file: {ANALYSIS_PATH}
test_required_output_files_exist

2. 第 103 行：f'Missing {ANALYSIS_PATH}
3. 第 104 行：f'Missing {SUMMARY_PATH}
test_output_schema_and_assumptions

4. 第 109 行：isinstance(data, dict)
5. 第 114 行：assumptions['patients_per_medication'] == PATIENTS
6. 第 115 行：assumptions['fills_per_year_90_day'] == FILLS_90
7. 第 116 行：assumptions['fills_per_year_100_day'] == FILLS_100
8. 第 117 行：assumptions['tablets_per_fill_90_day'] == TABLETS_90
9. 第 118 行：assumptions['tablets_per_fill_100_day'] == TABLETS_100
10. 第 119 行：assumptions['switch_threshold_usd'] == THRESHOLD
test_all_medications_present_and_unique

11. 第 125 行：medications must be a list
12. 第 126 行：f'Expected 10 medications, got {len(meds)}
13. 第 129 行：Medication names must be unique
14. 第 132 行：set(names) == expected_names
test_totals_consistent_with_rows

15. 第 183 行：close(totals['total_annual_revenue_90_day_usd'], sum_90)
16. 第 184 行：close(totals['total_annual_revenue_100_day_usd'], sum_100)
17. 第 185 行：close(totals['total_annual_revenue_difference_100_minus_90_usd'], sum_diff)
18. 第 186 行：close(totals['absolute_total_revenue_difference_usd'], abs_diff)
test_decision_rule_applied_correctly

19. 第 197 行：recommendation['decision'] in {'switch_to_100_day', 'keep_90_day'}
20. 第 198 行：recommendation['decision'] == expected_decision
21. 第 199 行：isinstance(recommendation['justification'], str)
22. 第 200 行：justification cannot be empty
test_summary_contains_key_outputs

23. 第 208 行：Summary must be 4 to 8 non-empty lines
24. 第 209 行：'Decision:' in summary
25. 第 212 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_output_schema_and_assumptions

26. 第 111 行：f'Missing top-level key: {key}；随行重复
test_per_medication_calculations

27. 第 158 行：f'Missing medication in output: {med}；随行重复
28. 第 164 行：row['vial_size_drams'] == exp['vial_size_drams']；随行重复
test_summary_contains_key_outputs

29. 第 221 行：f'Summary missing value {formatted}；随行重复
test_per_medication_calculations

30. 第 162 行：f'{med}: missing field {field}；随行重复
31. 第 168 行：f'{med} {field} mismatch: actual={row[field]} expected={exp[field]}；随行重复

### harbor_infusionbatch_7v14

断言 19 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_infusionbatch_7v14/tests/test_outputs.py

load_output

1. 第 107 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 112 行：OUTPUT_JSON.exists()
3. 第 113 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 118 行：set(data.keys()) == {'assumptions', 'therapies', 'totals', 'recommendation'}
5. 第 119 行：data['assumptions'] == {'deliveries_per_year_7_day': DELIVERIES_7, 'deliveries_per_year_14_day': DELIVERIES_14, 'days_per_delivery_7_day': DAYS_7, 'days_per_delivery_14_day': DAYS_
test_rows_and_order

6. 第 132 行：[r['therapy_code'] for r in data['therapies']] == [r['therapy_code'] for r in expected_rows]
test_totals_and_decision

7. 第 148 行：close(totals['total_annual_margin_7_day_usd'], total_7)
8. 第 149 行：close(totals['total_annual_margin_14_day_usd'], total_14)
9. 第 150 行：close(totals['total_annual_margin_difference_14_minus_7_usd'], total_diff)
10. 第 151 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 152 行：data['recommendation']['decision'] == decision
12. 第 153 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 160 行：4 <= len(lines) <= 8
14. 第 163 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 134 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 165 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 137 行：actual[key] == expected_value；随行重复
18. 第 139 行：actual[key] == expected_value；随行重复
19. 第 141 行：close(actual[key], expected_value)；随行重复

### harbor_mailerfill_45v90

断言 18 处，其中 4 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_mailerfill_45v90/tests/test_outputs.py

load_output

1. 第 91 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 96 行：OUTPUT_JSON.exists()
3. 第 97 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 102 行：set(data.keys()) == {'assumptions', 'medications', 'totals', 'recommendation'}
5. 第 103 行：data['assumptions'] == {'patients_per_medication': PATIENTS, 'fills_per_year_45_day': FILLS_45, 'fills_per_year_90_day': FILLS_90, 'doses_per_fill_45_day': DOSES_45, 'doses_per_fil
test_rows_and_order

6. 第 116 行：[row['medication'] for row in data['medications']] == [row['medication'] for row in expected_rows]
test_totals_and_decision

7. 第 130 行：close(totals['total_annual_margin_45_day_usd'], total_45)
8. 第 131 行：close(totals['total_annual_margin_90_day_usd'], total_90)
9. 第 132 行：close(totals['total_annual_margin_difference_90_minus_45_usd'], total_diff)
10. 第 133 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 134 行：data['recommendation']['decision'] == decision
12. 第 135 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 142 行：4 <= len(lines) <= 8
14. 第 145 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 118 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 147 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 121 行：actual[key] == expected_value；随行重复
18. 第 123 行：close(actual[key], expected_value)；随行重复

### harbor_oncocooler_10v20

断言 19 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_oncocooler_10v20/tests/test_outputs.py

load_output

1. 第 107 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 112 行：OUTPUT_JSON.exists()
3. 第 113 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 118 行：set(data.keys()) == {'assumptions', 'programs', 'totals', 'recommendation'}
5. 第 119 行：data['assumptions'] == {'dispatches_per_year_10_day': DISPATCHES_10, 'dispatches_per_year_20_day': DISPATCHES_20, 'days_per_dispatch_10_day': DAYS_10, 'days_per_dispatch_20_day': D
test_rows_and_order

6. 第 132 行：[row['program_code'] for row in data['programs']] == [row['program_code'] for row in expected_rows]
test_totals_and_decision

7. 第 148 行：close(totals['total_annual_margin_10_day_usd'], total_10)
8. 第 149 行：close(totals['total_annual_margin_20_day_usd'], total_20)
9. 第 150 行：close(totals['total_annual_margin_difference_20_minus_10_usd'], total_diff)
10. 第 151 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 152 行：data['recommendation']['decision'] == decision
12. 第 153 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 160 行：4 <= len(lines) <= 8
14. 第 163 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 134 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 165 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 137 行：actual[key] == expected_value；随行重复
18. 第 139 行：actual[key] == expected_value；随行重复
19. 第 141 行：close(actual[key], expected_value)；随行重复

### harbor_reagentkit_bulk

断言 20 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_reagentkit_bulk/tests/test_outputs.py

load_output

1. 第 114 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 119 行：OUTPUT_JSON.exists()
3. 第 120 行：OUTPUT_SUMMARY.exists()
test_metadata_and_schema

4. 第 126 行：data['metadata'] == metadata
5. 第 127 行：set(data['analysis'].keys()) == {'assumptions', 'assays', 'totals', 'recommendation'}
6. 第 128 行：data['analysis']['assumptions'] == {'runs_per_year_small_kit': RUNS_SMALL, 'runs_per_year_bulk_kit': RUNS_BULK, 'switch_threshold_usd': THRESHOLD, 'lab_override_rule': 'highest app
test_rows_and_order

7. 第 140 行：[r['assay_id'] for r in data['analysis']['assays']] == [r['assay_id'] for r in expected_rows]
test_totals_and_decision

8. 第 156 行：close(totals['total_annual_margin_small_kit_usd'], total_small)
9. 第 157 行：close(totals['total_annual_margin_bulk_kit_usd'], total_bulk)
10. 第 158 行：close(totals['total_annual_margin_difference_bulk_minus_small_usd'], total_diff)
11. 第 159 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
12. 第 160 行：data['analysis']['recommendation']['decision'] == decision
13. 第 161 行：data['analysis']['recommendation']['justification'].strip()
test_summary_requirements

14. 第 168 行：4 <= len(lines) <= 8
15. 第 171 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

16. 第 142 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

17. 第 173 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

18. 第 145 行：actual[key] == expected_value；随行重复
19. 第 147 行：actual[key] == expected_value；随行重复
20. 第 149 行：close(actual[key], expected_value)；随行重复

### harbor_syncpack_28v56

断言 19 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_syncpack_28v56/tests/test_outputs.py

load_output

1. 第 81 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 86 行：OUTPUT_JSON.exists()
3. 第 87 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 92 行：set(data.keys()) == {'assumptions', 'medications', 'totals', 'recommendation'}
5. 第 93 行：data['assumptions'] == {'patients_per_medication': PATIENTS, 'fills_per_year_28_day': FILLS_28, 'fills_per_year_56_day': FILLS_56, 'capsules_per_fill_28_day': CAPS_28, 'capsules_pe
test_rows_and_order

6. 第 106 行：[r['medication'] for r in data['medications']] == [r['medication'] for r in expected_rows]
test_totals_and_decision

7. 第 122 行：close(totals['total_annual_margin_28_day_usd'], total_28)
8. 第 123 行：close(totals['total_annual_margin_56_day_usd'], total_56)
9. 第 124 行：close(totals['total_annual_margin_difference_56_minus_28_usd'], total_diff)
10. 第 125 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 126 行：data['recommendation']['decision'] == decision
12. 第 127 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 134 行：4 <= len(lines) <= 8
14. 第 137 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 108 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 139 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 111 行：actual[key] == expected_value；随行重复
18. 第 113 行：actual[key] == expected_value；随行重复
19. 第 115 行：close(actual[key], expected_value)；随行重复

### harbor_vaxcrate_6v12

断言 19 处，其中 5 处在循环内。源文件：Healthcare-Cost-Benefit-Analysis/harbor_vaxcrate_6v12/tests/test_outputs.py

load_output

1. 第 122 行：OUTPUT_JSON.exists()
test_required_output_files_exist

2. 第 127 行：OUTPUT_JSON.exists()
3. 第 128 行：OUTPUT_SUMMARY.exists()
test_schema_and_assumptions

4. 第 133 行：set(data.keys()) == {'assumptions', 'campaigns', 'totals', 'recommendation'}
5. 第 134 行：data['assumptions'] == {'dispatches_per_year_6_day': DISPATCHES_6, 'dispatches_per_year_12_day': DISPATCHES_12, 'days_per_dispatch_6_day': DAYS_6, 'days_per_dispatch_12_day': DAYS_
test_rows_and_order

6. 第 148 行：[row['campaign_id'] for row in data['campaigns']] == [row['campaign_id'] for row in expected_rows]
test_totals_and_decision

7. 第 164 行：close(totals['total_annual_margin_6_day_usd'], total_6)
8. 第 165 行：close(totals['total_annual_margin_12_day_usd'], total_12)
9. 第 166 行：close(totals['total_annual_margin_difference_12_minus_6_usd'], total_diff)
10. 第 167 行：close(totals['absolute_total_margin_difference_usd'], abs_diff)
11. 第 168 行：data['recommendation']['decision'] == decision
12. 第 169 行：data['recommendation']['justification'].strip()
test_summary_requirements

13. 第 176 行：4 <= len(lines) <= 8
14. 第 179 行：f"Decision '{decision}' (or '{normalized}') not found in summary
test_rows_and_order

15. 第 150 行：set(actual.keys()) == set(expected.keys())；随行重复
test_summary_requirements

16. 第 181 行：f'{value:,.2f}' in text；随行重复
test_rows_and_order

17. 第 153 行：actual[key] == expected_value；随行重复
18. 第 155 行：actual[key] == expected_value；随行重复
19. 第 157 行：close(actual[key], expected_value)；随行重复

## DMAIC-Quality-Analysis

### harbor_devops_pipeline_02

断言 44 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_devops_pipeline_02/tests/test_outputs.py

outputs

1. 第 65 行：f'Missing output JSON: {JSON_OUTPUT}
2. 第 66 行：f'Missing output Markdown: {MD_OUTPUT}
assert_close

3. 第 147 行：f'expected {expected}, got {actual}
test_process1_metrics

4. 第 170 行：p1['n'] == exp['n']
5. 第 176 行：p1['trend_direction'] == exp['direction']
6. 第 177 行：p1['stability'] == exp['stability']
7. 第 178 行：'t-test' in p1['stability_method'].lower()
test_process2_metrics

8. 第 186 行：p2['points'] == exp['points']
9. 第 187 行：p2['total_lines'] == exp['total_denom']
10. 第 188 行：p2['total_bugs'] == exp['total_num']
11. 第 190 行：len(p2['wilson_95_ci_pct']) == 2
12. 第 194 行：p2['uses_varying_denominators'] == exp['varying_denominators']
13. 第 196 行：p2['capability_vs_target'] == exp['capability_vs_target']
14. 第 199 行：p2['trend_direction'] == exp['direction']
15. 第 200 行：p2['stability'] == exp['stability']
test_process3_metrics

16. 第 208 行：p3['rows'] == exp['rows']
17. 第 214 行：p3['trend_direction'] == exp['direction']
18. 第 215 行：p3['stability'] == exp['stability']
test_variability_ranking_and_highest_risk

19. 第 223 行：len(ranking) == 3
20. 第 224 行：[r['process'] for r in ranking] == [r['process'] for r in expected_ranking]
21. 第 229 行：report['highest_variability_process'] == expected_ranking[0]['process']
22. 第 230 行：report['highest_variability_process'].strip().lower() == 'deployment_failures'
23. 第 231 行：'Deployment Failures is the highest-risk stage.' in report['highest_risk_statement']
test_extended_analysis_consistency

24. 第 239 行：ext['process'] == highest
25. 第 240 行：isinstance(ext['capability_evaluation'], str) and len(ext['capability_evaluation']) > 20
26. 第 241 行：isinstance(ext['stability_assessment'], str) and len(ext['stability_assessment']) > 20
27. 第 242 行：isinstance(ext['priority_reason'], str) and len(ext['priority_reason']) > 20
28. 第 243 行：ext['time_trend_review']['direction'] in {'increasing', 'decreasing', 'flat'}
test_improvement_plan_schema

29. 第 264 行：isinstance(ip['prioritized_actions'], list) and len(ip['prioritized_actions']) >= 3
30. 第 265 行：isinstance(ip['methodology'], str) and len(ip['methodology']) > 20
31. 第 266 行：isinstance(ip['root_cause_approach'], str) and len(ip['root_cause_approach']) > 20
32. 第 267 行：isinstance(ip['incident_response_plan'], str) and len(ip['incident_response_plan']) > 20
33. 第 268 行：isinstance(ip['technical_debt_assessment'], str) and len(ip['technical_debt_assessment']) > 20
34. 第 269 行：isinstance(ip['project_codename'], str) and len(ip['project_codename']) > 0
35. 第 270 行：all((k in ip['momentum_plan_30_60_90'] for k in ['day_30', 'day_60', 'day_90']))
test_markdown_sections_and_required_text

36. 第 286 行：'Deployment Failures is the highest-risk stage.' in markdown
37. 第 300 行：re.search('project codename\\s*:', markdown, flags=re.IGNORECASE)
38. 第 301 行：re.search('30-day milestone', markdown, flags=re.IGNORECASE)
39. 第 302 行：re.search('60-day milestone', markdown, flags=re.IGNORECASE)
40. 第 303 行：re.search('90-day milestone', markdown, flags=re.IGNORECASE)
test_required_top_level_keys

41. 第 162 行：f'Missing top-level key: {key}；随行重复
test_improvement_plan_schema

42. 第 262 行：f'Missing improvement_plan key: {key}；随行重复
test_markdown_sections_and_required_text

43. 第 284 行：f'Missing markdown heading: {heading}；随行重复
44. 第 298 行：f'Missing markdown heading: {heading}；随行重复

### harbor_field_service_analyze_03

断言 21 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_field_service_analyze_03/tests/test_outputs.py

_assert_close

1. 第 110 行：f'{label} is not finite: {actual}
2. 第 111 行：f'{label} mismatch: {actual} vs {expected}
_assert_imr_limit

3. 第 142 行：%s mismatch: %s vs %s or %s' % (label, actual, unrounded, textbook)
test_output_files_exist

4. 第 148 行：f'Missing {OUT_JSON}
5. 第 149 行：f'Missing {OUT_MD}
test_json_structure_and_values

6. 第 169 行：os.path.basename(str(payload.get('source_file') or '')) == 'field_service_data.csv'
7. 第 176 行：_record_count(counts, 'primary_business_day_records', ('primary_business_days',)) == primary_biz
8. 第 177 行：_record_count(counts, 'imr_records', ('imr_business_days', 'imr_business_day_records')) == imr_records
9. 第 189 行：payload['anova_by_weekday']['highest_mean_day'] == expected['highest_day']
10. 第 190 行：payload['anova_by_weekday']['lowest_mean_day'] == expected['lowest_day']
11. 第 198 行：payload['imr_summary']['points'] == expected['imr_points']
12. 第 213 行：payload['ttest_vs_target']['n'] == expected['n']
13. 第 220 行：payload['ttest_vs_target']['decision'] == expected_decision
test_markdown_structure_and_content

14. 第 256 行：Need at least two required operational impacts in markdown
15. 第 262 行：Need at least two March 2025 due dates in next steps
16. 第 263 行：Next steps must include owners
test_json_structure_and_values

17. 第 167 行：f'Missing top-level key: {key}；随行重复
18. 第 175 行：total_got == total_primary
test_markdown_structure_and_content

19. 第 242 行：f'Missing header: {h}；随行重复
20. 第 252 行：f'Missing subsection: {s}；随行重复
21. 第 259 行：f'Missing timeline date: {d}；随行重复

### harbor_gdpval_35

断言 21 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_gdpval_35/tests/test_outputs.py

_assert_close

1. 第 105 行：f'{label} is not finite: {actual}
2. 第 106 行：f'{label} mismatch: {actual} vs {expected}
_assert_imr_limit

3. 第 137 行：%s mismatch: %s vs %s or %s' % (label, actual, unrounded, textbook)
test_output_files_exist

4. 第 143 行：f'Missing {OUT_JSON}
5. 第 144 行：f'Missing {OUT_MD}
test_json_structure_and_values

6. 第 164 行：os.path.basename(str(payload.get('source_file') or '')) == 'Processing_Data.xlsx'
7. 第 171 行：_record_count(counts, 'primary_business_day_records', ('primary_business_days',)) == primary_biz
8. 第 172 行：_record_count(counts, 'imr_records', ('imr_business_days', 'imr_business_day_records')) == imr_records
9. 第 184 行：payload['anova_by_weekday']['highest_mean_day'] == expected['highest_day']
10. 第 185 行：payload['anova_by_weekday']['lowest_mean_day'] == expected['lowest_day']
11. 第 193 行：payload['imr_summary']['points'] == expected['imr_points']
12. 第 208 行：payload['ttest_vs_target']['n'] == expected['n']
13. 第 215 行：payload['ttest_vs_target']['decision'] == expected_decision
test_markdown_structure_and_content

14. 第 257 行：Need at least two required operational impacts in markdown
15. 第 263 行：Need at least two March 2025 due dates in next steps
16. 第 264 行：Next steps must include owners
test_json_structure_and_values

17. 第 162 行：f'Missing top-level key: {key}；随行重复
18. 第 170 行：total_got == total_primary
test_markdown_structure_and_content

19. 第 237 行：f'Missing header: {h}；随行重复
20. 第 247 行：f'Missing subsection: {s}；随行重复
21. 第 260 行：f'Missing timeline date: {d}；随行重复

### harbor_gdpval_37

断言 43 处，其中 3 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_gdpval_37/tests/test_outputs.py

outputs

1. 第 65 行：f'Missing output JSON: {JSON_OUTPUT}
2. 第 66 行：f'Missing output Markdown: {MD_OUTPUT}
assert_close

3. 第 147 行：f'expected {expected}, got {actual}
test_task_duration_metrics

4. 第 170 行：td['n'] == exp['n']
5. 第 176 行：td['trend_direction'] == exp['direction']
6. 第 177 行：td['stability'] == exp['stability']
7. 第 178 行：'t-test' in td['stability_method'].lower()
test_failure_rate_metrics

8. 第 186 行：fr['points'] == exp['points']
9. 第 187 行：fr['total_units'] == exp['total_units']
10. 第 188 行：fr['total_failures'] == exp['total_fails']
11. 第 190 行：len(fr['wilson_95_ci_pct']) == 2
12. 第 194 行：fr['uses_varying_denominators'] == exp['varying_denominators']
13. 第 196 行：fr['capability_vs_target'] == exp['capability_vs_target']
14. 第 199 行：fr['trend_direction'] == exp['direction']
15. 第 200 行：fr['stability'] == exp['stability']
test_system_error_metrics

16. 第 208 行：se['rows'] == exp['rows']
17. 第 214 行：se['trend_direction'] == exp['direction']
18. 第 215 行：se['stability'] == exp['stability']
test_variability_ranking_and_highest_risk

19. 第 223 行：len(ranking) == 3
20. 第 224 行：[r['process'] for r in ranking] == [r['process'] for r in expected_ranking]
21. 第 229 行：report['highest_variability_process'] == expected_ranking[0]['process']
22. 第 230 行：report['highest_variability_process'].strip().lower() == 'system_errors'
23. 第 231 行：'System Errors is the highest-risk process.' in report['highest_risk_statement']
test_extended_analysis_consistency

24. 第 239 行：ext['process'] == highest
25. 第 240 行：isinstance(ext['capability_evaluation'], str) and len(ext['capability_evaluation']) > 20
26. 第 241 行：isinstance(ext['stability_assessment'], str) and len(ext['stability_assessment']) > 20
27. 第 242 行：isinstance(ext['priority_reason'], str) and len(ext['priority_reason']) > 20
28. 第 243 行：ext['time_trend_review']['direction'] in {'increasing', 'decreasing', 'flat'}
test_monitoring_plan_schema

29. 第 269 行：isinstance(mp['inputs'], list) and len(mp['inputs']) >= 2
30. 第 270 行：isinstance(mp['outputs'], list) and len(mp['outputs']) >= 2
31. 第 271 行：isinstance(mp['key_performance_indicators'], list) and len(mp['key_performance_indicators']) >= 3
32. 第 272 行：isinstance(mp['prioritized_actions'], list) and len(mp['prioritized_actions']) >= 3
33. 第 273 行：5 <= len(mp['checklist']) <= 9
34. 第 274 行：all((k in mp['momentum_plan_30_60_90'] for k in ['day_30', 'day_60', 'day_90']))
35. 第 275 行：isinstance(mp['project_codename'], str) and len(mp['project_codename']) > 0
test_markdown_sections_and_required_text

36. 第 302 行：'System Errors is the highest-risk process.' in markdown
37. 第 303 行：re.search('project codename\\s*:', markdown, flags=re.IGNORECASE)
38. 第 304 行：re.search('30-day milestone', markdown, flags=re.IGNORECASE)
39. 第 305 行：re.search('60-day milestone', markdown, flags=re.IGNORECASE)
40. 第 306 行：re.search('90-day milestone', markdown, flags=re.IGNORECASE)
test_required_top_level_keys

41. 第 162 行：f'Missing top-level key: {key}；随行重复
test_monitoring_plan_schema

42. 第 267 行：f'Missing monitoring_plan key: {key}；随行重复
test_markdown_sections_and_required_text

43. 第 300 行：f'Missing markdown heading: {heading}；随行重复

### harbor_hospital_lab_analyze_02

断言 21 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_hospital_lab_analyze_02/tests/test_outputs.py

_assert_close

1. 第 110 行：f'{label} is not finite: {actual}
2. 第 111 行：f'{label} mismatch: {actual} vs {expected}
_assert_imr_limit

3. 第 142 行：%s mismatch: %s vs %s or %s' % (label, actual, unrounded, textbook)
test_output_files_exist

4. 第 148 行：f'Missing {OUT_JSON}
5. 第 149 行：f'Missing {OUT_MD}
test_json_structure_and_values

6. 第 169 行：os.path.basename(str(payload.get('source_file') or '')) == 'lab_panel_data.csv'
7. 第 176 行：_record_count(counts, 'primary_business_day_records', ('primary_business_days',)) == primary_biz
8. 第 177 行：_record_count(counts, 'imr_records', ('imr_business_days', 'imr_business_day_records')) == imr_records
9. 第 189 行：payload['anova_by_weekday']['highest_mean_day'] == expected['highest_day']
10. 第 190 行：payload['anova_by_weekday']['lowest_mean_day'] == expected['lowest_day']
11. 第 198 行：payload['imr_summary']['points'] == expected['imr_points']
12. 第 213 行：payload['ttest_vs_target']['n'] == expected['n']
13. 第 220 行：payload['ttest_vs_target']['decision'] == expected_decision
test_markdown_structure_and_content

14. 第 256 行：Need at least two required operational impacts in markdown
15. 第 262 行：Need at least two March 2025 due dates in next steps
16. 第 263 行：Next steps must include owners
test_json_structure_and_values

17. 第 167 行：f'Missing top-level key: {key}；随行重复
18. 第 175 行：total_got == total_primary
test_markdown_structure_and_content

19. 第 242 行：f'Missing header: {h}；随行重复
20. 第 252 行：f'Missing subsection: {s}；随行重复
21. 第 259 行：f'Missing timeline date: {d}；随行重复

### harbor_hospital_safety_01

断言 38 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_hospital_safety_01/tests/test_outputs.py

outputs

1. 第 65 行：f'Missing output JSON: {JSON_OUTPUT}
2. 第 66 行：f'Missing output Markdown: {MD_OUTPUT}
assert_close

3. 第 147 行：f'expected {expected}, got {actual}
test_process1_metrics

4. 第 170 行：p1['n'] == exp['n']
5. 第 176 行：p1['trend_direction'] == exp['direction']
6. 第 177 行：p1['stability'] == exp['stability']
7. 第 178 行：'t-test' in p1['stability_method'].lower()
test_process2_metrics

8. 第 186 行：p2['points'] == exp['points']
9. 第 187 行：p2['total_prescriptions'] == exp['total_denom']
10. 第 188 行：p2['total_errors'] == exp['total_num']
11. 第 190 行：len(p2['wilson_95_ci_pct']) == 2
12. 第 194 行：p2['uses_varying_denominators'] == exp['varying_denominators']
13. 第 196 行：p2['capability_vs_target'] == exp['capability_vs_target']
14. 第 199 行：p2['trend_direction'] == exp['direction']
15. 第 200 行：p2['stability'] == exp['stability']
test_process3_metrics

16. 第 208 行：p3['rows'] == exp['rows']
17. 第 214 行：p3['trend_direction'] == exp['direction']
18. 第 215 行：p3['stability'] == exp['stability']
test_variability_ranking_and_highest_risk

19. 第 223 行：len(ranking) == 3
20. 第 224 行：[r['process'] for r in ranking] == [r['process'] for r in expected_ranking]
21. 第 229 行：report['highest_variability_process'] == expected_ranking[0]['process']
22. 第 230 行：report['highest_variability_process'].strip().lower() == 'readmission_rates'
23. 第 231 行：'Readmission Rates is the highest-risk department.' in report['highest_risk_statement']
test_extended_analysis_consistency

24. 第 239 行：ext['process'] == highest
25. 第 240 行：isinstance(ext['capability_evaluation'], str) and len(ext['capability_evaluation']) > 20
26. 第 241 行：isinstance(ext['stability_assessment'], str) and len(ext['stability_assessment']) > 20
27. 第 242 行：isinstance(ext['priority_reason'], str) and len(ext['priority_reason']) > 20
28. 第 243 行：ext['time_trend_review']['direction'] in {'increasing', 'decreasing', 'flat'}
test_monitoring_plan_schema

29. 第 267 行：isinstance(mp['inputs'], list) and len(mp['inputs']) >= 2
30. 第 268 行：isinstance(mp['outputs'], list) and len(mp['outputs']) >= 2
31. 第 269 行：isinstance(mp['key_performance_indicators'], list) and len(mp['key_performance_indicators']) >= 3
32. 第 270 行：isinstance(mp['prioritized_actions'], list) and len(mp['prioritized_actions']) >= 3
33. 第 271 行：5 <= len(mp['checklist']) <= 9
test_markdown_sections_and_required_text

34. 第 288 行：'Readmission Rates is the highest-risk department.' in markdown
test_required_top_level_keys

35. 第 162 行：f'Missing top-level key: {key}；随行重复
test_monitoring_plan_schema

36. 第 265 行：f'Missing monitoring_plan key: {key}；随行重复
test_markdown_sections_and_required_text

37. 第 286 行：f'Missing markdown heading: {heading}；随行重复
38. 第 305 行：f'Missing markdown heading: {heading}；随行重复

### harbor_logistics_chain_03

断言 45 处，其中 3 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_logistics_chain_03/tests/test_outputs.py

outputs

1. 第 65 行：f'Missing output JSON: {JSON_OUTPUT}
2. 第 66 行：f'Missing output Markdown: {MD_OUTPUT}
assert_close

3. 第 147 行：f'expected {expected}, got {actual}
test_process1_metrics

4. 第 171 行：p1['n'] == exp['n']
5. 第 177 行：p1['trend_direction'] == exp['direction']
6. 第 178 行：p1['stability'] == exp['stability']
7. 第 179 行：'t-test' in p1['stability_method'].lower()
test_process2_metrics

8. 第 187 行：p2['points'] == exp['points']
9. 第 188 行：p2['total_shipments'] == exp['total_denom']
10. 第 189 行：p2['total_damaged'] == exp['total_num']
11. 第 191 行：len(p2['wilson_95_ci_pct']) == 2
12. 第 195 行：p2['uses_varying_denominators'] == exp['varying_denominators']
13. 第 197 行：p2['capability_vs_target'] == exp['capability_vs_target']
14. 第 200 行：p2['trend_direction'] == exp['direction']
15. 第 201 行：p2['stability'] == exp['stability']
test_process3_metrics

16. 第 209 行：p3['rows'] == exp['rows']
17. 第 215 行：p3['trend_direction'] == exp['direction']
18. 第 216 行：p3['stability'] == exp['stability']
test_variability_ranking_and_highest_risk

19. 第 224 行：len(ranking) == 3
20. 第 225 行：[r['process'] for r in ranking] == [r['process'] for r in expected_ranking]
21. 第 230 行：report['highest_variability_process'] == expected_ranking[0]['process']
22. 第 231 行：report['highest_variability_process'].strip().lower() == 'order_accuracy'
23. 第 232 行：'Order Accuracy is the highest-risk process.' in report['highest_risk_statement']
test_extended_analysis_consistency

24. 第 240 行：ext['process'] == highest
25. 第 241 行：isinstance(ext['capability_evaluation'], str) and len(ext['capability_evaluation']) > 20
26. 第 242 行：isinstance(ext['stability_assessment'], str) and len(ext['stability_assessment']) > 20
27. 第 243 行：isinstance(ext['priority_reason'], str) and len(ext['priority_reason']) > 20
28. 第 244 行：ext['time_trend_review']['direction'] in {'increasing', 'decreasing', 'flat'}
test_variance_diagnostic_schema

29. 第 264 行：isinstance(vd['amplification_detected'], bool)
30. 第 265 行：vd['severity'] in {'none', 'low', 'moderate', 'high', 'critical'}
31. 第 266 行：isinstance(vd['recommended_intervention'], str) and len(vd['recommended_intervention']) > 10
test_action_plan_schema

32. 第 273 行：isinstance(ap['prioritized_actions'], list) and len(ap['prioritized_actions']) >= 3
33. 第 274 行：5 <= len(ap['checklist']) <= 9
34. 第 275 行：isinstance(ap['project_codename'], str) and len(ap['project_codename']) > 0
35. 第 276 行：all((k in ap['momentum_plan_30_60_90'] for k in ['day_30', 'day_60', 'day_90']))
test_markdown_sections_and_required_text

36. 第 291 行：'Order Accuracy is the highest-risk process.' in markdown
37. 第 293 行：Missing heading: Variance Diagnostic
38. 第 294 行：Missing heading: Action Plan
39. 第 296 行：re.search('project codename\\s*:', markdown, flags=re.IGNORECASE)
40. 第 297 行：re.search('30-day milestone', markdown, flags=re.IGNORECASE)
41. 第 298 行：re.search('60-day milestone', markdown, flags=re.IGNORECASE)
42. 第 299 行：re.search('90-day milestone', markdown, flags=re.IGNORECASE)
test_required_top_level_keys

43. 第 163 行：f'Missing top-level key: {key}；随行重复
test_variance_diagnostic_schema

44. 第 262 行：f'Missing variance_diagnostic key: {key}；随行重复
test_markdown_sections_and_required_text

45. 第 289 行：f'Missing markdown heading: {heading}；随行重复

### harbor_soc_alert_analyze_01

断言 21 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_soc_alert_analyze_01/tests/test_outputs.py

_assert_close

1. 第 110 行：f'{label} is not finite: {actual}
2. 第 111 行：f'{label} mismatch: {actual} vs {expected}
_assert_imr_limit

3. 第 142 行：%s mismatch: %s vs %s or %s' % (label, actual, unrounded, textbook)
test_output_files_exist

4. 第 148 行：f'Missing {OUT_JSON}
5. 第 149 行：f'Missing {OUT_MD}
test_json_structure_and_values

6. 第 169 行：os.path.basename(str(payload.get('source_file') or '')) == 'soc_alert_data.csv'
7. 第 176 行：_record_count(counts, 'primary_business_day_records', ('primary_business_days',)) == primary_biz
8. 第 177 行：_record_count(counts, 'imr_records', ('imr_business_days', 'imr_business_day_records')) == imr_records
9. 第 189 行：payload['anova_by_weekday']['highest_mean_day'] == expected['highest_day']
10. 第 190 行：payload['anova_by_weekday']['lowest_mean_day'] == expected['lowest_day']
11. 第 198 行：payload['imr_summary']['points'] == expected['imr_points']
12. 第 213 行：payload['ttest_vs_target']['n'] == expected['n']
13. 第 220 行：payload['ttest_vs_target']['decision'] == expected_decision
test_markdown_structure_and_content

14. 第 256 行：Need at least two required operational impacts in markdown
15. 第 262 行：Need at least two March 2025 due dates in next steps
16. 第 263 行：Next steps must include owners
test_json_structure_and_values

17. 第 167 行：f'Missing top-level key: {key}；随行重复
18. 第 175 行：total_got == total_primary
test_markdown_structure_and_content

19. 第 242 行：f'Missing header: {h}；随行重复
20. 第 252 行：f'Missing subsection: {s}；随行重复
21. 第 259 行：f'Missing timeline date: {d}；随行重复

### harbor_university_it_analyze_04

断言 21 处，其中 4 处在循环内。源文件：DMAIC-Quality-Analysis/harbor_university_it_analyze_04/tests/test_outputs.py

_assert_close

1. 第 110 行：f'{label} is not finite: {actual}
2. 第 111 行：f'{label} mismatch: {actual} vs {expected}
_assert_imr_limit

3. 第 142 行：%s mismatch: %s vs %s or %s' % (label, actual, unrounded, textbook)
test_output_files_exist

4. 第 148 行：f'Missing {OUT_JSON}
5. 第 149 行：f'Missing {OUT_MD}
test_json_structure_and_values

6. 第 169 行：os.path.basename(str(payload.get('source_file') or '')) == 'it_helpdesk_data.csv'
7. 第 176 行：_record_count(counts, 'primary_business_day_records', ('primary_business_days',)) == primary_biz
8. 第 177 行：_record_count(counts, 'imr_records', ('imr_business_days', 'imr_business_day_records')) == imr_records
9. 第 189 行：payload['anova_by_weekday']['highest_mean_day'] == expected['highest_day']
10. 第 190 行：payload['anova_by_weekday']['lowest_mean_day'] == expected['lowest_day']
11. 第 198 行：payload['imr_summary']['points'] == expected['imr_points']
12. 第 213 行：payload['ttest_vs_target']['n'] == expected['n']
13. 第 220 行：payload['ttest_vs_target']['decision'] == expected_decision
test_markdown_structure_and_content

14. 第 256 行：Need at least two required operational impacts in markdown
15. 第 262 行：Need at least two March 2025 due dates in next steps
16. 第 263 行：Next steps must include owners
test_json_structure_and_values

17. 第 167 行：f'Missing top-level key: {key}；随行重复
18. 第 175 行：total_got == total_primary
test_markdown_structure_and_content

19. 第 242 行：f'Missing header: {h}；随行重复
20. 第 252 行：f'Missing subsection: {s}；随行重复
21. 第 259 行：f'Missing timeline date: {d}；随行重复

## SEC-13F-Financial-Analysis

### cross-quarter-reconciliation

断言 4 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/cross-quarter-reconciliation/tests/test_outputs.py

test_file_exists

1. 第 13 行：OUTPUT_FILE.is_file()
test_answers

2. 第 19 行：answers['comparison_pairs'] == gt['comparison_pairs']
3. 第 20 行：answers['issuer_checks'] == gt['issuer_checks']
4. 第 21 行：answers['snapshot_check'] == gt['snapshot_check']

### deduped-alert-pack

断言 2 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/deduped-alert-pack/tests/test_outputs.py

test_file_exists

1. 第 11 行：OUTPUT_FILE.is_file()
test_answers

2. 第 15 行：load_json(OUTPUT_FILE) == load_json(GROUND_TRUTH)

### existing-brief-refresh

断言 2 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/existing-brief-refresh/tests/test_outputs.py

test_file_exists

1. 第 42 行：OUTPUT_FILE.is_file()
test_answers

2. 第 49 行：msg

### fund-class-breakdown

断言 2 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/fund-class-breakdown/tests/test_outputs.py

test_file_exists

1. 第 42 行：OUTPUT_FILE.is_file()
test_answers

2. 第 49 行：msg

### fund-shift-screen

断言 5 处，其中 1 处在循环内。源文件：SEC-13F-Financial-Analysis/fund-shift-screen/tests/test_outputs.py

test_file_exists

1. 第 13 行：OUTPUT_FILE.is_file()
test_answers

2. 第 21 行：answers['top4_increased_cusips'] == gt['top4_increased_cusips']
3. 第 22 行：answers['top3_decreased_cusips'] == gt['top3_decreased_cusips']
4. 第 23 行：answers['new_positions_top2'] == gt['new_positions_top2']
5. 第 20 行：answers[key] == gt[key]；随行重复

### fund-snapshot-canonical

断言 22 处，其中 3 处在循环内。源文件：SEC-13F-Financial-Analysis/fund-snapshot-canonical/tests/test_outputs.py

test_file_exists

1. 第 14 行：OUTPUT_FILE.is_file()
test_json_schema

2. 第 38 行：f"top3_cusips_by_value should have 3 items, got {len(answers['top3_cusips_by_value'])}
test_manager_matching

3. 第 51 行：matched_manager should not be empty
4. 第 52 行：accession_number should not be empty
5. 第 55 行：f"Manager mismatch: got '{answers['matched_manager']}', expected '{gt['matched_manager']}
6. 第 57 行：f"Accession number mismatch: got '{answers['accession_number']}', expected '{gt['accession_number']}
test_stock_holdings_count

7. 第 68 行：f"Stock holdings count too different: got {answers['stock_holdings']}, expected {gt['stock_holdings']} (diff={count_diff})
test_aum_values

8. 第 79 行：f"AUM mismatch: got {answers['aum']}, expected {gt['aum']} (diff={aum_diff})
9. 第 84 行：f"Stock AUM mismatch: got {answers['stock_aum']}, expected {gt['stock_aum']} (diff={stock_aum_diff})
test_top3_cusips

10. 第 94 行：f"Top CUSIP mismatch: got {answers['top3_cusips_by_value'][0]}, expected {gt['top3_cusips_by_value'][0]}
11. 第 99 行：f"Top 3 CUSIPs set mismatch: got {answers['top3_cusips_by_value']}, expected {gt['top3_cusips_by_value']}
test_full_output

12. 第 108 行：answers['fund_query'] == gt['fund_query']
13. 第 109 行：answers['quarter'] == gt['quarter']
14. 第 110 行：answers['matched_manager'] == gt['matched_manager']
15. 第 111 行：answers['accession_number'] == gt['accession_number']
16. 第 112 行：abs(answers['aum'] - gt['aum']) < 0.001
17. 第 113 行：abs(answers['stock_holdings'] - gt['stock_holdings']) <= 5
18. 第 114 行：abs(answers['stock_aum'] - gt['stock_aum']) < 0.001
19. 第 115 行：set(answers['top3_cusips_by_value']) == set(gt['top3_cusips_by_value'])
test_json_schema

20. 第 33 行：f'Missing required key: {key}；随行重复
21. 第 34 行：f"Key '{key}' has wrong type: expected {expected_type}, got {type(answers[key])}；随行重复
22. 第 41 行：f'top3_cusips_by_value[{i}] should be string, got {type(cusip)}；随行重复

### issuer-ownership-rollup

断言 6 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/issuer-ownership-rollup/tests/test_outputs.py

test_file_exists

1. 第 13 行：OUTPUT_FILE.is_file()
test_answers

2. 第 19 行：answers['issuer_query'] == gt['issuer_query']
3. 第 20 行：answers['quarter'] == gt['quarter']
4. 第 21 行：answers['cusip'] == gt['cusip']
5. 第 22 行：answers['top5_managers'] == gt['top5_managers']
6. 第 23 行：answers['top5_accessions'] == gt['top5_accessions']

### manager-pair-issuer-grid

断言 2 处，其中 0 处在循环内。源文件：SEC-13F-Financial-Analysis/manager-pair-issuer-grid/tests/test_outputs.py

test_file_exists

1. 第 42 行：OUTPUT_FILE.is_file()
test_answers

2. 第 49 行：msg

## Compensation-Scenario-Modeling

### 01_orchestra_foundation_model

断言 45 处，其中 10 处在循环内。源文件：Compensation-Scenario-Modeling/01_orchestra_foundation_model/tests/test_outputs.py

output_wb

1. 第 19 行：f'Missing required output file: {OUTPUT_FILE}
source_wb

2. 第 25 行：f'Missing required source file: {SOURCE_FILE}
test_sheet_names

3. 第 30 行：output_wb.sheetnames == ['Summary', 'Assumptions', 'Roster', 'Calculations --->', 'EE Calcs (Current)', 'EE Calcs (Yr+1)', 'EE Calcs (Yr+2)']
test_summary_structure_and_formulas

4. 第 96 行：ws['B1'].value == 'Renaissance Popular Orchestra - Musician Compensation'
5. 第 97 行：ws['C5'].value == 2395
6. 第 98 行：norm_formula(ws['D5'].value) == '=C5*(1+D6)'
7. 第 99 行：norm_formula(ws['E5'].value) == '=D5*(1+E6)'
8. 第 100 行：ws['D6'].value == 0.05
9. 第 101 行：ws['E6'].value == 0.05
10. 第 102 行：norm_formula(ws['D12'].value) == '=WHLim_Yr1*1.03'
11. 第 103 行：norm_formula(ws['E12'].value) == '=D12*1.03'
test_roster_and_assumptions_migration

12. 第 157 行：'Renaissance Popular Orchestra' in str(out_assump['B1'].value)
13. 第 158 行：out_assump['B3'].value == src_assump['B3'].value
14. 第 159 行：'Payroll Tax' in str(out_assump['B18'].value)
test_calc_sheet_formulas

15. 第 186 行：ws['A3'].value == 'Employee #'
16. 第 187 行：ws['B3'].value == 'Titled Positions'
17. 第 188 行：ws['C3'].value == 'Overscale'
18. 第 189 行：ws['D3'].value == 'Years of Service'
19. 第 190 行：ws['E3'].value == 'Notes'
20. 第 191 行：ws['F3'].value == 'Principal'
21. 第 192 行：ws['G3'].value == 'Seniority'
22. 第 202 行：f'MWS_{year_token}' in str(ws['F4'].value)
23. 第 203 行：f'Sr5to9_{year_token}' in str(ws['G4'].value)
24. 第 204 行：norm_formula(ws['H4'].value) == f'=MWS_{year_token}*13'
25. 第 205 行：norm_formula(ws['L4'].value) == '=IF(ISBLANK($E4),$C4*13,($C4-$F4)*13)'
26. 第 206 行：norm_formula(ws['P4'].value) == '=$F4*13'
27. 第 207 行：norm_formula(ws['T4'].value) == f'=Media_{year_token}*13'
28. 第 208 行：norm_formula(ws['AB4'].value) == '=SUMIFS($H4:$AA4,$H$3:$AA$3,AB$3)'
29. 第 209 行：f'WHto7k_{year_token}' in str(ws['AF4'].value)
30. 第 210 行：f'WHLim_{year_token}' in str(ws['AF4'].value)
31. 第 211 行：f'WHoverLim_{year_token}' in str(ws['AF4'].value)
test_defined_names

32. 第 88 行：f'Missing defined name: {name}；随行重复
33. 第 90 行：f'Defined name {name} expected {expected_ref}, got {actual}；随行重复
test_summary_structure_and_formulas

34. 第 114 行：ws[f'B{i}'].value == label；随行重复
35. 第 137 行：norm_formula(ws[f'{col}32'].value) == f'=SUM({col}26:{col}31)'；随行重复
36. 第 150 行：norm_formula(ws[cell].value) == formula；随行重复
test_roster_and_assumptions_migration

37. 第 162 行：out_assump[f'C{row}'].value == src_assump[f'C{row}'].value；随行重复
38. 第 163 行：out_assump[f'D{row}'].value == src_assump[f'D{row}'].value；随行重复
39. 第 172 行：f'Roster row mismatch at output row {i}；随行重复
test_calc_sheet_formulas

40. 第 195 行：isinstance(ws['D4'].value, (int, float))
41. 第 198 行：d4 is not None
42. 第 199 行：norm_formula(service_ref) in d4
43. 第 200 行：'+1' in d4
44. 第 216 行：norm_formula(ws[f'{col}107'].value) == expected；随行重复
test_summary_structure_and_formulas

45. 第 133 行：norm_formula(ws[f'{summary_col}{row_num}'].value) == norm_formula(expected_formula)；随行重复

### 02_orchestra_archive_refresh_model

断言 45 处，其中 10 处在循环内。源文件：Compensation-Scenario-Modeling/02_orchestra_archive_refresh_model/tests/test_outputs.py

output_wb

1. 第 19 行：f'Missing required output file: {OUTPUT_FILE}
source_wb

2. 第 25 行：f'Missing required source file: {SOURCE_FILE}
test_sheet_names

3. 第 30 行：output_wb.sheetnames == ['Summary', 'Assumptions', 'Roster', 'Calculations --->', 'EE Calcs (Current)', 'EE Calcs (Yr+1)', 'EE Calcs (Yr+2)']
test_summary_structure_and_formulas

4. 第 96 行：ws['B1'].value == 'Festival Civic Orchestra - Musician Compensation'
5. 第 97 行：ws['C5'].value == 2395
6. 第 98 行：norm_formula(ws['D5'].value) == '=C5*(1+D6)'
7. 第 99 行：norm_formula(ws['E5'].value) == '=D5*(1+E6)'
8. 第 100 行：ws['D6'].value == 0.05
9. 第 101 行：ws['E6'].value == 0.05
10. 第 102 行：norm_formula(ws['D12'].value) == '=WHLim_Yr1*1.03'
11. 第 103 行：norm_formula(ws['E12'].value) == '=D12*1.03'
test_roster_and_assumptions_migration

12. 第 157 行：'Festival Civic Orchestra' in str(out_assump['B1'].value)
13. 第 158 行：out_assump['B3'].value == src_assump['B3'].value
14. 第 159 行：'Payroll Tax' in str(out_assump['B18'].value)
test_calc_sheet_formulas

15. 第 186 行：ws['A3'].value == 'Employee #'
16. 第 187 行：ws['B3'].value == 'Titled Positions'
17. 第 188 行：ws['C3'].value == 'Overscale'
18. 第 189 行：ws['D3'].value == 'Years of Service'
19. 第 190 行：ws['E3'].value == 'Notes'
20. 第 191 行：ws['F3'].value == 'Principal'
21. 第 192 行：ws['G3'].value == 'Seniority'
22. 第 202 行：f'MWS_{year_token}' in str(ws['F4'].value)
23. 第 203 行：f'Sr5to9_{year_token}' in str(ws['G4'].value)
24. 第 204 行：norm_formula(ws['H4'].value) == f'=MWS_{year_token}*13'
25. 第 205 行：norm_formula(ws['L4'].value) == '=IF(ISBLANK($E4),$C4*13,($C4-$F4)*13)'
26. 第 206 行：norm_formula(ws['P4'].value) == '=$F4*13'
27. 第 207 行：norm_formula(ws['T4'].value) == f'=Media_{year_token}*13'
28. 第 208 行：norm_formula(ws['AB4'].value) == '=SUMIFS($H4:$AA4,$H$3:$AA$3,AB$3)'
29. 第 209 行：f'WHto7k_{year_token}' in str(ws['AF4'].value)
30. 第 210 行：f'WHLim_{year_token}' in str(ws['AF4'].value)
31. 第 211 行：f'WHoverLim_{year_token}' in str(ws['AF4'].value)
test_defined_names

32. 第 88 行：f'Missing defined name: {name}；随行重复
33. 第 90 行：f'Defined name {name} expected {expected_ref}, got {actual}；随行重复
test_summary_structure_and_formulas

34. 第 114 行：ws[f'B{i}'].value == label；随行重复
35. 第 137 行：norm_formula(ws[f'{col}32'].value) == f'=SUM({col}26:{col}31)'；随行重复
36. 第 150 行：norm_formula(ws[cell].value) == formula；随行重复
test_roster_and_assumptions_migration

37. 第 162 行：out_assump[f'C{row}'].value == src_assump[f'C{row}'].value；随行重复
38. 第 163 行：out_assump[f'D{row}'].value == src_assump[f'D{row}'].value；随行重复
39. 第 172 行：f'Roster row mismatch at output row {i}；随行重复
test_calc_sheet_formulas

40. 第 195 行：isinstance(ws['D4'].value, (int, float))
41. 第 198 行：d4 is not None
42. 第 199 行：norm_formula(service_ref) in d4
43. 第 200 行：'+1' in d4
44. 第 216 行：norm_formula(ws[f'{col}107'].value) == expected；随行重复
test_summary_structure_and_formulas

45. 第 133 行：norm_formula(ws[f'{summary_col}{row_num}'].value) == norm_formula(expected_formula)；随行重复

### 03_university_faculty_model

断言 14 处，其中 2 处在循环内。源文件：Compensation-Scenario-Modeling/03_university_faculty_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >= 50 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 25 行：Summary B1 should contain organization name
test_summary_base_salary

5. 第 30 行：f"Expected C5=62000, got {ws['C5'].value}
6. 第 31 行：f"Expected D5='=C5*1.03', got {ws['D5'].value}
test_summary_comp_rows

7. 第 36 行：Summary row 26 should have component label
8. 第 37 行：Summary row 32 should have component label
9. 第 38 行：Summary row 33 should have total label
test_ee_calcs_row_count

10. 第 45 行：f'Expected >=75 data rows, got {data_rows}
test_quarterly_totals_row

11. 第 53 行：Row 79 (quarterly totals) should exist in EE Calcs
test_roster_migrated

12. 第 60 行：f'Expected >=75 roster entries, got {count}
test_ee_calcs_yoy_service_progression

13. 第 74 行：f'Row {r}: Yr+1 service should be +1 (got {v1}->{v2})；随行重复
14. 第 76 行：f'Row {r}: Yr+1 service should be +1 (got {v1}->{v2})；随行重复

### 04_university_termload_refresh_model

断言 13 处，其中 1 处在循环内。源文件：Compensation-Scenario-Modeling/04_university_termload_refresh_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >= 50 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 25 行：ws['B1'].value == 'Lakeshore State University - Faculty Compensation'
test_summary_base_salary

5. 第 30 行：f"Expected C5=62000, got {ws['C5'].value}
6. 第 31 行：f"Expected D5='=C5*1.03', got {ws['D5'].value}
test_summary_comp_rows

7. 第 36 行：Summary row 26 should have component label
8. 第 37 行：Summary row 32 should have component label
9. 第 38 行：Summary row 33 should have total label
test_ee_calcs_row_count

10. 第 45 行：f'Expected >=75 data rows, got {data_rows}
test_quarterly_totals_row

11. 第 53 行：Row 79 (quarterly totals) should exist in EE Calcs
test_roster_migrated

12. 第 60 行：f'Expected >=75 roster entries, got {count}
test_ee_calcs_yoy_service_progression

13. 第 71 行：f'Row {r}: Yr+1 service should be +1 (got {v1}->{v2})；随行重复

### 05_property_management_model

断言 11 处，其中 2 处在循环内。源文件：Compensation-Scenario-Modeling/05_property_management_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >=46 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 27 行：Summary B1 should contain organization name
5. 第 28 行：f"Expected C5=52000, got {ws['C5'].value}
6. 第 29 行：f"Expected D5='=C5*1.03
test_ee_calcs_row_count

7. 第 36 行：f'Expected >=87 data rows, got {data_rows}
test_quarterly_totals_row_91

8. 第 42 行：Row 91 (quarterly totals) should exist in EE Calcs
test_roster_count

9. 第 57 行：f'Expected >=87 roster entries, got {count}
test_summary_references_row_91

10. 第 50 行：f'Summary row 33 should reference EE Calcs row 91, got {v}；随行重复
test_yoy_service_progression

11. 第 68 行：f'Yr+1 service should be +1；随行重复

### 06_property_portfolio_refresh_model

断言 11 处，其中 2 处在循环内。源文件：Compensation-Scenario-Modeling/06_property_portfolio_refresh_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >=46 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 26 行：ws['B1'].value == 'Harborfront Portfolio Services - Staff Compensation'
5. 第 27 行：f"Expected C5=52000, got {ws['C5'].value}
6. 第 28 行：f"Expected D5='=C5*1.03
test_ee_calcs_row_count

7. 第 35 行：f'Expected >=87 data rows, got {data_rows}
test_quarterly_totals_row_91

8. 第 41 行：Row 91 (quarterly totals) should exist in EE Calcs
test_roster_count

9. 第 56 行：f'Expected >=87 roster entries, got {count}
test_summary_references_row_91

10. 第 49 行：f'Summary row 33 should reference EE Calcs row 91, got {v}；随行重复
test_yoy_service_progression

11. 第 66 行：f'Yr+1 service should be +1；随行重复

### 07_airline_crew_model

断言 11 处，其中 2 处在循环内。源文件：Compensation-Scenario-Modeling/07_airline_crew_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >=65 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 27 行：Summary B1 should contain organization name
5. 第 28 行：f"Expected C5=78000, got {ws['C5'].value}
6. 第 29 行：f"Expected D5='=C5*1.03
test_ee_calcs_row_count

7. 第 36 行：f'Expected >=65 data rows, got {data_rows}
test_quarterly_totals_row_69

8. 第 42 行：Row 69 (quarterly totals) should exist in EE Calcs
test_roster_count

9. 第 57 行：f'Expected >=65 roster entries, got {count}
test_summary_references_row_69

10. 第 50 行：f'Summary row 32 should reference EE Calcs row 69, got {v}；随行重复
test_yoy_service_progression

11. 第 68 行：f'Yr+1 service should be +1；随行重复

### 08_construction_union_model

断言 13 处，其中 2 处在循环内。源文件：Compensation-Scenario-Modeling/08_construction_union_model/tests/test_outputs.py

test_file_exists

1. 第 10 行：f'Output file not found: {OUTPUT_FILE}
test_sheet_names

2. 第 16 行：f'Expected {expected}, got {wb.sheetnames}
test_named_ranges_count

3. 第 20 行：f'Expected >=85 named ranges, got {len(wb.defined_names)}
test_summary_title

4. 第 27 行：Summary B1 should contain organization name
5. 第 28 行：f"Expected C5=48.00, got {ws['C5'].value}
6. 第 29 行：f"Expected D5='=C5*1.03
test_summary_comp_rows

7. 第 34 行：Summary B26 should have component label
8. 第 35 行：Summary B34 should have TOTAL label
test_ee_calcs_row_count

9. 第 42 行：f'Expected >=90 data rows, got {data_rows}
test_quarterly_totals_row_94

10. 第 48 行：Row 94 (quarterly totals) should exist in EE Calcs
test_roster_count

11. 第 63 行：f'Expected >=90 roster entries, got {count}
test_summary_references_row_94

12. 第 56 行：f'Summary row 34 should reference EE Calcs row 94, got {v}；随行重复
test_yoy_service_progression

13. 第 74 行：f'Yr+1 service should be +1；随行重复

## Weighted-Risk-Assessment

### api-sla-at-risk-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/api-sla-at-risk-calc/tests/test_outputs.py

assert_matrix

1. 第 157 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 161 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 163 行：wb.sheetnames == ['Task', 'Data']
4. 第 165 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 191 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 209 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 233 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 218 行：f'{ref} lost yellow fill；随行重复
9. 第 219 行：f'{ref} fill changed: {rgb}；随行重复

### campus-budget-at-risk-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/campus-budget-at-risk-calc/tests/test_outputs.py

assert_matrix

1. 第 158 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 162 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 164 行：wb.sheetnames == ['Task', 'Data']
4. 第 166 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 192 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 210 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 234 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 219 行：f'{ref} lost yellow fill；随行重复
9. 第 220 行：f'{ref} fill changed: {rgb}；随行重复

### factory-output-at-risk-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/factory-output-at-risk-calc/tests/test_outputs.py

assert_matrix

1. 第 157 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 161 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 163 行：wb.sheetnames == ['Task', 'Data']
4. 第 165 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 191 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 209 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 233 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 218 行：f'{ref} lost yellow fill；随行重复
9. 第 219 行：f'{ref} fill changed: {rgb}；随行重复

### hospital-capacity-at-risk-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/hospital-capacity-at-risk-calc/tests/test_outputs.py

assert_matrix

1. 第 157 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 161 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 163 行：wb.sheetnames == ['Task', 'Data']
4. 第 165 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 191 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 209 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 233 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 218 行：f'{ref} lost yellow fill；随行重复
9. 第 219 行：f'{ref} fill changed: {rgb}；随行重复

### weighted-campus-energy-balance-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/weighted-campus-energy-balance-calc/tests/test_outputs.py

assert_matrix

1. 第 157 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 161 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 163 行：wb.sheetnames == ['Task', 'Data']
4. 第 165 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 191 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 209 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 233 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 218 行：f'{ref} lost yellow fill；随行重复
9. 第 219 行：f'{ref} fill changed: {rgb}；随行重复

### weighted-cloud-reliability-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/weighted-cloud-reliability-calc/tests/test_outputs.py

assert_matrix

1. 第 157 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 161 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 163 行：wb.sheetnames == ['Task', 'Data']
4. 第 165 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 191 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 209 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 233 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 218 行：f'{ref} lost yellow fill；随行重复
9. 第 219 行：f'{ref} fill changed: {rgb}；随行重复

### weighted-hospital-bedflow-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/weighted-hospital-bedflow-calc/tests/test_outputs.py

assert_matrix

1. 第 86 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 90 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 92 行：wb.sheetnames == ['Task', 'Data']
4. 第 94 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 120 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 138 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 162 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 147 行：f'{ref} lost yellow fill；随行重复
9. 第 148 行：f'{ref} fill changed: {rgb}；随行重复

### weighted-port-throughput-calc

断言 9 处，其中 2 处在循环内。源文件：Weighted-Risk-Assessment/weighted-port-throughput-calc/tests/test_outputs.py

assert_matrix

1. 第 156 行：f'{label} mismatches:\n' + '\n'.join(errors)
test_file_and_sheet_structure

2. 第 160 行：f'Missing output workbook: {EXCEL_FILE}
3. 第 162 行：wb.sheetnames == ['Task', 'Data']
4. 第 164 行：ws['A1'].value is not None
test_derived_values_and_stats

5. 第 190 行：weighted mean mismatches:\n' + '\n'.join(weighted_errors)
test_formulas_present_in_editable_ranges

6. 第 208 行：Missing formulas:\n' + '\n'.join(missing)
test_no_excel_errors_or_macros

7. 第 232 行：Validation errors:\n' + '\n'.join(errors)
test_template_formatting_preserved

8. 第 217 行：f'{ref} lost yellow fill；随行重复
9. 第 218 行：f'{ref} fill changed: {rgb}；随行重复

## Embedded-Data-Repair

### buffer-dilution-matrix-repair

断言 11 处，其中 0 处在循环内。源文件：Embedded-Data-Repair/buffer-dilution-matrix-repair/tests/test_outputs.py

test_output_file_exists

1. 第 83 行：results.pptx was not created
test_output_is_valid_pptx

2. 第 87 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 75 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 79 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_is_valid_pptx

5. 第 89 行：Embedded workbook is missing from the output
test_target_rate_and_inverse_are_updated

6. 第 99 行：f'Direct rate cell is empty (no cached value)
7. 第 100 行：f'Direct rate was not updated correctly: expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved

8. 第 153 行：Formula cells changed or were replaced with values
test_target_rate_and_inverse_are_updated

9. 第 105 行：f'Inverse rate was not updated correctly: expected {1.0 / EXPECTED_RATE}, got {inverse_value}
10. 第 115 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
11. 第 124 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### catalyst-balance-matrix-sync

断言 12 处，其中 1 处在循环内。源文件：Embedded-Data-Repair/catalyst-balance-matrix-sync/tests/test_outputs.py

test_output_exists_and_contains_target_embedding

1. 第 82 行：results.pptx was not created
2. 第 83 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 74 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 78 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_exists_and_contains_target_embedding

5. 第 85 行：Target embedding is missing from the output
test_target_pair_updated

6. 第 95 行：f'Direct rate cell is empty (no cached value)
7. 第 96 行：f'Expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved_in_target_embedding

8. 第 145 行：Formula cells changed or were replaced with values
test_other_values_and_archive_embeddings_unchanged

9. 第 182 行：f'Archive embedding {embedding_name} should be unchanged；随行重复
test_target_pair_updated

10. 第 99 行：f'Expected {1.0 / EXPECTED_RATE}, got {inverse_value}
11. 第 107 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
12. 第 116 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### emission-zone-dual-matrix-repair

断言 10 处，其中 0 处在循环内。源文件：Embedded-Data-Repair/emission-zone-dual-matrix-repair/tests/test_outputs.py

test_output_exists

1. 第 84 行：results.pptx was not created
2. 第 85 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 76 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 80 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_live_matrix_updated_and_archive_matrix_unchanged

5. 第 97 行：f'Direct rate cell is empty (no cached value)
6. 第 98 行：f'Expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved

7. 第 164 行：Formula cells changed or were replaced with values
test_live_matrix_updated_and_archive_matrix_unchanged

8. 第 101 行：f'Expected {1.0 / EXPECTED_RATE}, got {inverse_value}
9. 第 109 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
10. 第 118 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### fx-cross-rate-inverse-fix

断言 11 处，其中 0 处在循环内。源文件：Embedded-Data-Repair/fx-cross-rate-inverse-fix/tests/test_outputs.py

test_output_file_exists

1. 第 83 行：results.pptx was not created
test_output_is_valid_pptx

2. 第 87 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 75 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 79 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_is_valid_pptx

5. 第 89 行：Embedded workbook is missing from the output
test_target_rate_and_inverse_are_updated

6. 第 99 行：f'Direct rate cell is empty (no cached value)
7. 第 100 行：f'Direct rate was not updated correctly: expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved

8. 第 153 行：Formula cells changed or were replaced with values
test_target_rate_and_inverse_are_updated

9. 第 105 行：f'Inverse rate was not updated correctly: expected {1.0 / EXPECTED_RATE}, got {inverse_value}
10. 第 115 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
11. 第 124 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### fx-spot-matrix-refresh

断言 11 处，其中 0 处在循环内。源文件：Embedded-Data-Repair/fx-spot-matrix-refresh/tests/test_outputs.py

test_output_file_exists

1. 第 83 行：results.pptx was not created
test_output_is_valid_pptx

2. 第 87 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 75 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 79 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_is_valid_pptx

5. 第 89 行：Embedded workbook is missing from the output
test_target_rate_and_inverse_are_updated

6. 第 99 行：f'Direct rate cell is empty (no cached value)
7. 第 100 行：f'Direct rate was not updated correctly: expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved

8. 第 153 行：Formula cells changed or were replaced with values
test_target_rate_and_inverse_are_updated

9. 第 105 行：f'Inverse rate was not updated correctly: expected {1.0 / EXPECTED_RATE}, got {inverse_value}
10. 第 115 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
11. 第 124 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### rebate-band-live-embedding-fix

断言 12 处，其中 1 处在循环内。源文件：Embedded-Data-Repair/rebate-band-live-embedding-fix/tests/test_outputs.py

test_output_exists_and_contains_target_embedding

1. 第 82 行：results.pptx was not created
2. 第 83 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 74 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 78 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_exists_and_contains_target_embedding

5. 第 85 行：Target embedding is missing from the output
test_target_pair_updated

6. 第 95 行：f'Direct rate cell is empty (no cached value)
7. 第 96 行：f'Expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved_in_target_embedding

8. 第 145 行：Formula cells changed or were replaced with values
test_other_values_and_archive_embeddings_unchanged

9. 第 182 行：f'Archive embedding {embedding_name} should be unchanged；随行重复
test_target_pair_updated

10. 第 99 行：f'Expected {1.0 / EXPECTED_RATE}, got {inverse_value}
11. 第 107 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
12. 第 116 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### supplier-pack-matrix-refresh

断言 11 处，其中 0 处在循环内。源文件：Embedded-Data-Repair/supplier-pack-matrix-refresh/tests/test_outputs.py

test_output_file_exists

1. 第 83 行：results.pptx was not created
test_output_is_valid_pptx

2. 第 87 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 75 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 79 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_is_valid_pptx

5. 第 89 行：Embedded workbook is missing from the output
test_target_rate_and_inverse_are_updated

6. 第 99 行：f'Direct rate cell is empty (no cached value)
7. 第 100 行：f'Direct rate was not updated correctly: expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved

8. 第 153 行：Formula cells changed or were replaced with values
test_target_rate_and_inverse_are_updated

9. 第 105 行：f'Inverse rate was not updated correctly: expected {1.0 / EXPECTED_RATE}, got {inverse_value}
10. 第 115 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
11. 第 124 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

### warehouse-slot-factor-refresh

断言 12 处，其中 1 处在循环内。源文件：Embedded-Data-Repair/warehouse-slot-factor-refresh/tests/test_outputs.py

test_output_exists_and_contains_target_embedding

1. 第 82 行：results.pptx was not created
2. 第 83 行：results.pptx is not a valid PPTX archive
assert_same

3. 第 74 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
4. 第 78 行：f'Unexpected change at {coord}: {lhs} -> {rhs}
test_output_exists_and_contains_target_embedding

5. 第 85 行：Target embedding is missing from the output
test_target_pair_updated

6. 第 95 行：f'Direct rate cell is empty (no cached value)
7. 第 96 行：f'Expected {EXPECTED_RATE}, got {direct_value}
test_formula_cells_preserved_in_target_embedding

8. 第 145 行：Formula cells changed or were replaced with values
test_other_values_and_archive_embeddings_unchanged

9. 第 182 行：f'Archive embedding {embedding_name} should be unchanged；随行重复
test_target_pair_updated

10. 第 99 行：f'Expected {1.0 / EXPECTED_RATE}, got {inverse_value}
11. 第 107 行：f'Inverse rate cell is neither a cached value nor a formula: {inverse_formula}
12. 第 116 行：f'Inverse formula does not reference the direct rate cell correctly: {inverse_formula}

## Inventory-&-Finance-Integration

### harbor_gdpval_21

断言 48 处，其中 24 处在循环内。源文件：Inventory-&-Finance-Integration/harbor_gdpval_21/tests/test_outputs.js

main

1. 第 87 行：${message} (actual=${actual}, expected=${expected})
2. 第 99 行：Missing sheet: Current Inventory
3. 第 100 行：Missing sheet: Incoming Shipments
4. 第 101 行：Missing sheet: Ratio
5. 第 105 行：Unable to parse AsOfDate
6. 第 106 行：Unable to parse PlanningHorizonEnd
7. 第 110 行：Invalid cases per pallet
8. 第 228 行：Workbook must contain exactly two sheets in required order
9. 第 253 行：Duplicate SKU in output: ${sku}；随行重复
10. 第 276 行：Input file not found: ${inputFile}
11. 第 277 行：Output file not found: ${outputFile}
12. 第 282 行：SKU_Results A1 must be Field
13. 第 283 行：SKU_Results B1 must be Value
14. 第 284 行：SKU_Results A2 label mismatch
15. 第 285 行：AsOfDate mismatch
16. 第 286 行：SKU_Results A3 label mismatch
17. 第 291 行：PlanningHorizonEnd mismatch
18. 第 296 行：SKU_Results A4 label mismatch
19. 第 301 行：RemainingDaysInJuly mismatch
20. 第 324 行：SKU_Results header mismatch
21. 第 331 行：SKU_Results row count mismatch
22. 第 343 行：SKU row order mismatch
23. 第 347 行：Missing SKU row in SKU_Results: ${exp.Product_SKU}；随行重复
24. 第 348 行：SKU mismatch for ${exp.Product_SKU}；随行重复
25. 第 349 行：Current_Cases mismatch for ${exp.Product_SKU}；随行重复
26. 第 350 行：Daily rate mismatch for ${exp.Product_SKU}；随行重复
27. 第 357 行：Current_DOH should be blank for ${exp.Product_SKU}；随行重复
28. 第 359 行：Current_DOH mismatch for ${exp.Product_SKU}；随行重复
29. 第 361 行：Projected_OOS_Date mismatch for ${exp.Product_SKU}；随行重复
30. 第 366 行：Inbound cases mismatch for ${exp.Product_SKU}；随行重复
31. 第 373 行：Delivered_DOH should be blank for ${exp.Product_SKU}；随行重复
32. 第 379 行：Delivered_DOH mismatch for ${exp.Product_SKU}；随行重复
33. 第 386 行：Remaining demand mismatch for ${exp.Product_SKU}；随行重复
34. 第 392 行：Additional cases mismatch for ${exp.Product_SKU}；随行重复
35. 第 398 行：Pallets required mismatch for ${exp.Product_SKU}；随行重复
36. 第 404 行：Required_Delivery_Date mismatch for ${exp.Product_SKU}；随行重复
37. 第 409 行：Rounding_Applied mismatch for ${exp.Product_SKU}；随行重复
38. 第 414 行：Earlier_Delivery_Required mismatch for ${exp.Product_SKU}；随行重复
39. 第 419 行：Earliest inbound mismatch for ${exp.Product_SKU}；随行重复
40. 第 434 行：Additional_Shipments_Needed header mismatch
41. 第 441 行：Additional sheet row count mismatch
42. 第 453 行：Additional sheet row order mismatch
43. 第 461 行：Missing SKU row in Additional_Shipments_Needed: ${exp.Product_SKU}；随行重复
44. 第 462 行：Additional sheet date mismatch for ${exp.Product_SKU}；随行重复
45. 第 467 行：Additional sheet pallets mismatch for ${exp.Product_SKU}；随行重复
46. 第 473 行：Additional sheet cases mismatch for ${exp.Product_SKU}；随行重复
47. 第 479 行：Additional sheet rounding flag mismatch for ${exp.Product_SKU}；随行重复
48. 第 484 行：Additional sheet earlier-delivery flag mismatch for ${exp.Product_SKU}；随行重复

### new_task_10_maintenance_calcfields_restock

断言 13 处，其中 4 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_10_maintenance_calcfields_restock/tests/test_outputs.js

main

1. 第 159 行：Missing one or more required sheets
2. 第 163 行：Unable to parse AsOfDate or PlanningHorizonEnd
3. 第 166 行：Invalid conversion ratio
4. 第 282 行：)
5. 第 287 行：assert.strictEqual(toBool(actual), expected, msg)
6. 第 291 行：assert(actual === null || actual === undefined || actual === "", msg)
7. 第 293 行：assert.strictEqual(toIsoDate(actual), expected, msg)
8. 第 296 行：assert.strictEqual(a, String(expected), msg)
9. 第 301 行： row count mismatch
10. 第 307 行： column count mismatch；随行重复
11. 第 320 行：Input file not found: ；随行重复
12. 第 321 行：Output file not found: ；随行重复
13. 第 326 行：Workbook must contain exactly two sheets in required order；随行重复

### new_task_10_transit_subsidy_rollforward

断言 36 处，其中 36 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_10_transit_subsidy_rollforward/tests/test_outputs.js

main

1. 第 65 行：Workbook not found: ${outputFile}；随行重复
2. 第 70 行：Sheet names/order must be exactly ${expectedSheets.join(", ")}；随行重复
3. 第 82 行：${sheetName} sheet missing；随行重复
4. 第 84 行：${sheetName}!A1 must be MetroLink Transit Authority；随行重复
5. 第 85 行：${sheetName}!A2 must include "${titleContains}"；随行重复
6. 第 124 行：${sheetName}!${col}${rowNumber} expected "${text(expected)}" got "${text(actual)}"；随行重复
7. 第 129 行：${sheetName}!${col}${rowNumber} expected ${num(expected)} got ${num(actual)}；随行重复
8. 第 155 行：${sheetName}!A${totalsRow} must be "Month Totals"；随行重复
9. 第 161 行：${sheetName}!${col}${totalsRow} formula mismatch；随行重复
10. 第 167 行：${sheetName}!A${endingRow} must be "Ending Balance"；随行重复
11. 第 171 行：${sheetName}!E${endingRow} formula mismatch；随行重复
12. 第 176 行：${sheetName}!H${endingRow} formula mismatch；随行重复
13. 第 181 行：${sheetName}!K${endingRow} formula mismatch；随行重复
14. 第 186 行：${sheetName}!N${endingRow} formula mismatch；随行重复
15. 第 191 行：${sheetName}!O${endingRow} formula mismatch；随行重复
16. 第 197 行：${sheetName}!A${varianceRow} must be "Variance"；随行重复
17. 第 201 行：${sheetName}!O${varianceRow} formula mismatch；随行重复
18. 第 207 行：${sheetName}!A${glRow} must be "GL Balance"；随行重复
19. 第 211 行：${sheetName}!E${glRow} GL Jan mismatch；随行重复
20. 第 212 行：${sheetName}!H${glRow} GL Feb mismatch；随行重复
21. 第 213 行：${sheetName}!K${glRow} GL Mar mismatch；随行重复
22. 第 214 行：${sheetName}!N${glRow} GL Apr mismatch；随行重复
23. 第 215 行：${sheetName}!O${glRow} formula mismatch；随行重复
24. 第 240 行：Transit Summary sheet missing；随行重复
25. 第 242 行：Transit Summary!A1 must be MetroLink Transit Authority；随行重复
26. 第 243 行：Transit Summary!A2 must include Summary；随行重复
27. 第 247 行：Transit Summary!A3 must include period through 4/30/2025；随行重复
28. 第 252 行：Transit Summary!A5 must be Description；随行重复
29. 第 253 行：Transit Summary!B5 must be Amount；随行重复
30. 第 255 行：Transit Summary!B7 formula mismatch；随行重复
31. 第 260 行：Transit Summary!B8 formula mismatch；随行重复
32. 第 265 行：Transit Summary!B9 formula mismatch；随行重复
33. 第 270 行：Transit Summary!B12 formula mismatch；随行重复
34. 第 275 行：Transit Summary!B13 formula mismatch；随行重复
35. 第 280 行：Transit Summary!B14 formula mismatch；随行重复
36. 第 285 行：Transit Summary!B16 formula must be B9+B14；随行重复

### new_task_11_datacenter_stochastic_refills

断言 13 处，其中 4 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_11_datacenter_stochastic_refills/tests/test_outputs.js

main

1. 第 167 行：Missing one or more required sheets
2. 第 171 行：Unable to parse AsOfDate or PlanningHorizonEnd
3. 第 174 行：Invalid conversion ratio
4. 第 290 行：)
5. 第 295 行：assert.strictEqual(toBool(actual), expected, msg)
6. 第 299 行：assert(actual === null || actual === undefined || actual === "", msg)
7. 第 301 行：assert.strictEqual(toIsoDate(actual), expected, msg)
8. 第 304 行：assert.strictEqual(a, String(expected), msg)
9. 第 309 行： row count mismatch
10. 第 315 行： column count mismatch；随行重复
11. 第 328 行：Input file not found: ；随行重复
12. 第 329 行：Output file not found: ；随行重复
13. 第 334 行：Workbook must contain exactly two sheets in required order；随行重复

### new_task_11_media_rights_rollforward

断言 36 处，其中 36 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_11_media_rights_rollforward/tests/test_outputs.js

main

1. 第 65 行：Workbook not found: ${outputFile}；随行重复
2. 第 70 行：Sheet names/order must be exactly ${expectedSheets.join(", ")}；随行重复
3. 第 82 行：${sheetName} sheet missing；随行重复
4. 第 84 行：${sheetName}!A1 must be Aurora Stream；随行重复
5. 第 85 行：${sheetName}!A2 must include "${titleContains}"；随行重复
6. 第 124 行：${sheetName}!${col}${rowNumber} expected "${text(expected)}" got "${text(actual)}"；随行重复
7. 第 129 行：${sheetName}!${col}${rowNumber} expected ${num(expected)} got ${num(actual)}；随行重复
8. 第 155 行：${sheetName}!A${totalsRow} must be "Month Totals"；随行重复
9. 第 161 行：${sheetName}!${col}${totalsRow} formula mismatch；随行重复
10. 第 167 行：${sheetName}!A${endingRow} must be "Ending Balance"；随行重复
11. 第 171 行：${sheetName}!E${endingRow} formula mismatch；随行重复
12. 第 176 行：${sheetName}!H${endingRow} formula mismatch；随行重复
13. 第 181 行：${sheetName}!K${endingRow} formula mismatch；随行重复
14. 第 186 行：${sheetName}!N${endingRow} formula mismatch；随行重复
15. 第 191 行：${sheetName}!O${endingRow} formula mismatch；随行重复
16. 第 197 行：${sheetName}!A${varianceRow} must be "Variance"；随行重复
17. 第 201 行：${sheetName}!O${varianceRow} formula mismatch；随行重复
18. 第 207 行：${sheetName}!A${glRow} must be "GL Balance"；随行重复
19. 第 211 行：${sheetName}!E${glRow} GL Jan mismatch；随行重复
20. 第 212 行：${sheetName}!H${glRow} GL Feb mismatch；随行重复
21. 第 213 行：${sheetName}!K${glRow} GL Mar mismatch；随行重复
22. 第 214 行：${sheetName}!N${glRow} GL Apr mismatch；随行重复
23. 第 215 行：${sheetName}!O${glRow} formula mismatch；随行重复
24. 第 240 行：Rights Summary sheet missing；随行重复
25. 第 242 行：Rights Summary!A1 must be Aurora Stream；随行重复
26. 第 243 行：Rights Summary!A2 must include Summary；随行重复
27. 第 247 行：Rights Summary!A3 must include period through 4/30/2025；随行重复
28. 第 252 行：Rights Summary!A5 must be Description；随行重复
29. 第 253 行：Rights Summary!B5 must be Amount；随行重复
30. 第 255 行：Rights Summary!B7 formula mismatch；随行重复
31. 第 260 行：Rights Summary!B8 formula mismatch；随行重复
32. 第 265 行：Rights Summary!B9 formula mismatch；随行重复
33. 第 270 行：Rights Summary!B12 formula mismatch；随行重复
34. 第 275 行：Rights Summary!B13 formula mismatch；随行重复
35. 第 280 行：Rights Summary!B14 formula mismatch；随行重复
36. 第 285 行：Rights Summary!B16 formula must be B9+B14；随行重复

### new_task_12_mealkit_freshness_replenishment

断言 13 处，其中 4 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_12_mealkit_freshness_replenishment/tests/test_outputs.js

main

1. 第 164 行：Missing one or more required sheets
2. 第 168 行：Unable to parse AsOfDate or PlanningHorizonEnd
3. 第 171 行：Invalid conversion ratio
4. 第 287 行：)
5. 第 292 行：assert.strictEqual(toBool(actual), expected, msg)
6. 第 296 行：assert(actual === null || actual === undefined || actual === "", msg)
7. 第 298 行：assert.strictEqual(toIsoDate(actual), expected, msg)
8. 第 301 行：assert.strictEqual(a, String(expected), msg)
9. 第 306 行： row count mismatch
10. 第 312 行： column count mismatch；随行重复
11. 第 325 行：Input file not found: ；随行重复
12. 第 326 行：Output file not found: ；随行重复
13. 第 331 行：Workbook must contain exactly two sheets in required order；随行重复

### new_task_9_datacenter_capacity_rollforward

断言 36 处，其中 36 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_9_datacenter_capacity_rollforward/tests/test_outputs.js

main

1. 第 65 行：Workbook not found: ${outputFile}；随行重复
2. 第 70 行：Sheet names/order must be exactly ${expectedSheets.join(", ")}；随行重复
3. 第 82 行：${sheetName} sheet missing；随行重复
4. 第 84 行：${sheetName}!A1 must be Nimbus Compute；随行重复
5. 第 85 行：${sheetName}!A2 must include "${titleContains}"；随行重复
6. 第 124 行：${sheetName}!${col}${rowNumber} expected "${text(expected)}" got "${text(actual)}"；随行重复
7. 第 129 行：${sheetName}!${col}${rowNumber} expected ${num(expected)} got ${num(actual)}；随行重复
8. 第 155 行：${sheetName}!A${totalsRow} must be "Month Totals"；随行重复
9. 第 161 行：${sheetName}!${col}${totalsRow} formula mismatch；随行重复
10. 第 167 行：${sheetName}!A${endingRow} must be "Ending Balance"；随行重复
11. 第 171 行：${sheetName}!E${endingRow} formula mismatch；随行重复
12. 第 176 行：${sheetName}!H${endingRow} formula mismatch；随行重复
13. 第 181 行：${sheetName}!K${endingRow} formula mismatch；随行重复
14. 第 186 行：${sheetName}!N${endingRow} formula mismatch；随行重复
15. 第 191 行：${sheetName}!O${endingRow} formula mismatch；随行重复
16. 第 197 行：${sheetName}!A${varianceRow} must be "Variance"；随行重复
17. 第 201 行：${sheetName}!O${varianceRow} formula mismatch；随行重复
18. 第 207 行：${sheetName}!A${glRow} must be "GL Balance"；随行重复
19. 第 211 行：${sheetName}!E${glRow} GL Jan mismatch；随行重复
20. 第 212 行：${sheetName}!H${glRow} GL Feb mismatch；随行重复
21. 第 213 行：${sheetName}!K${glRow} GL Mar mismatch；随行重复
22. 第 214 行：${sheetName}!N${glRow} GL Apr mismatch；随行重复
23. 第 215 行：${sheetName}!O${glRow} formula mismatch；随行重复
24. 第 240 行：Capacity Summary sheet missing；随行重复
25. 第 242 行：Capacity Summary!A1 must be Nimbus Compute；随行重复
26. 第 243 行：Capacity Summary!A2 must include Summary；随行重复
27. 第 247 行：Capacity Summary!A3 must include period through 4/30/2025；随行重复
28. 第 252 行：Capacity Summary!A5 must be Description；随行重复
29. 第 253 行：Capacity Summary!B5 must be Amount；随行重复
30. 第 255 行：Capacity Summary!B7 formula mismatch；随行重复
31. 第 260 行：Capacity Summary!B8 formula mismatch；随行重复
32. 第 265 行：Capacity Summary!B9 formula mismatch；随行重复
33. 第 270 行：Capacity Summary!B12 formula mismatch；随行重复
34. 第 275 行：Capacity Summary!B13 formula mismatch；随行重复
35. 第 280 行：Capacity Summary!B14 formula mismatch；随行重复
36. 第 285 行：Capacity Summary!B16 formula must be B9+B14；随行重复

### new_task_9_hospital_staffing_resilience

断言 13 处，其中 4 处在循环内。源文件：Inventory-&-Finance-Integration/new_task_9_hospital_staffing_resilience/tests/test_outputs.js

main

1. 第 159 行：Missing one or more required sheets
2. 第 163 行：Unable to parse AsOfDate or PlanningHorizonEnd
3. 第 166 行：Invalid conversion ratio
4. 第 282 行：)
5. 第 287 行：assert.strictEqual(toBool(actual), expected, msg)
6. 第 291 行：assert(actual === null || actual === undefined || actual === "", msg)
7. 第 293 行：assert.strictEqual(toIsoDate(actual), expected, msg)
8. 第 296 行：assert.strictEqual(a, String(expected), msg)
9. 第 301 行： row count mismatch
10. 第 307 行： column count mismatch；随行重复
11. 第 320 行：Input file not found: ；随行重复
12. 第 321 行：Output file not found: ；随行重复
13. 第 326 行：Workbook must contain exactly two sheets in required order；随行重复

## Operational-Recovery-Planning

### harbor_ag_recovery_03

断言 55 处，其中 22 处在循环内。源文件：Operational-Recovery-Planning/harbor_ag_recovery_03/tests/test_outputs.py

assert_formula_contains

1. 第 37 行：f'{cell_ref} must be a formula.
workbook

2. 第 113 行：f'Output workbook not found: {OUTPUT_XLSX}
due_map

3. 第 120 行：f'Reference workbook missing: {REFERENCE_XLSX}
summary_text

4. 第 127 行：f'Summary markdown not found: {OUTPUT_SUMMARY}
test_sheet_names

5. 第 132 行：set(workbook.sheetnames) == set(SHEET_NAMES)
test_sheet_layout_and_rules

6. 第 139 行：f'{sheet_name}: expected exactly {LAST_ROW} rows.
7. 第 141 行：ws['C2'].value == 'Wheat Bin Loads'
8. 第 142 行：ws['F2'].value == 'Canola Bin Loads'
9. 第 143 行：ws['I2'].value == 'Flax Processing'
10. 第 157 行：f'{sheet_name}: header mismatch in C3:K3.
11. 第 160 行：f'{sheet_name}: B4 must be {START_DATE}.
extract_section

12. 第 290 行：f'Missing section header: ## Scenario {scenario_number}
test_summary_structure_and_required_statements

13. 第 313 行：Scenario 1 must contain 'May PO On-Time: No'.
14. 第 316 行：Scenario 2 must contain 'May PO On-Time: Wheat Yes, Canola No'.
15. 第 321 行：Scenario 3 must contain 'May PO On-Time: Yes'.
16. 第 324 行：Scenario 3 must explicitly mention '30-day notification'.
assert_formula_contains

17. 第 39 行：f"{cell_ref} formula is missing token '{token}'. Got: {value}；随行重复
parse_nonnegative_int

18. 第 48 行：f'{cell_ref} must be a whole number.
19. 第 49 行：f'{cell_ref} must be nonnegative.
20. 第 53 行：f'{cell_ref} must be a numeric constant, not a formula.
21. 第 60 行：f'{cell_ref} must be a whole number.
22. 第 61 行：f'{cell_ref} must be nonnegative.
test_sheet_layout_and_rules

23. 第 204 行：f'{sheet_name}: wrong Wheat due on {d}. Expected {expected_a_due}, got {a_due}.；随行重复
24. 第 207 行：f'{sheet_name}: wrong Canola due on {d}. Expected {expected_b_due}, got {b_due}.；随行重复
25. 第 255 行：f'{sheet_name}: total Flax Processing output must be >= 1200.
26. 第 256 行：f'{sheet_name}: expected Flax Processing to run on at least 10 days.
27. 第 257 行：f'{sheet_name}: Canola Bin Loads production starts too early.
28. 第 260 行：f'{sheet_name}: expected both Wheat and Canola backlogs to remain > 0 by May 1.
29. 第 265 行：f'{sheet_name}: must produce at least 100 Flax Processing units pre-relocation.
30. 第 266 行：f'{sheet_name}: Flax Processing output must be 0 on/after 2018-02-01.
31. 第 267 行：f'{sheet_name}: Canola Bin Loads production starts too early.
32. 第 270 行：f'{sheet_name}: expected Wheat backlog cleared and Canola backlog remaining by May 1.
33. 第 275 行：f'{sheet_name}: Flax Processing output must be zero for entire horizon.
34. 第 276 行：f'{sheet_name}: expected 20-24 high-output (10-hour shift) days, got {high_output_days}.
35. 第 279 行：f'{sheet_name}: Canola Bin Loads production starts too early.
36. 第 282 行：f'{sheet_name}: expected both Wheat and Canola backlogs cleared by May 1.
37. 第 212 行：f'{sheet_name}: Wheat production must be 0 on non-working day {d}.；随行重复
38. 第 213 行：f'{sheet_name}: Canola production must be 0 on non-working day {d}.；随行重复
39. 第 214 行：f'{sheet_name}: Flax production must be 0 on non-working day {d}.；随行重复
test_summary_structure_and_required_statements

40. 第 309 行：f"Scenario {idx} is missing required field '{label}'.；随行重复
test_sheet_layout_and_rules

41. 第 178 行：f'{sheet_name}: B{row} has incorrect date.；随行重复
42. 第 181 行：f'{sheet_name}: B{row} must be date or formula.；随行重复
43. 第 182 行：f'{sheet_name}: B{row} must advance date by 1 day.；随行重复
44. 第 218 行：f'{sheet_name}: Wheat output exceeds 120 on {d}.；随行重复
45. 第 219 行：f'{sheet_name}: Canola output exceeds 120 on {d}.；随行重复
46. 第 221 行：f'{sheet_name}: Wheat output exceeds 135 on {d}.；随行重复
47. 第 222 行：f'{sheet_name}: Canola output exceeds 135 on {d}.；随行重复
48. 第 226 行：f'{sheet_name}: 10-hour output used before 2018-02-01.；随行重复
49. 第 227 行：f'{sheet_name}: high-output day must be a working day ({d}).；随行重复
50. 第 230 行：f'{sheet_name}: Wheat output exceeds 170 on {d}.；随行重复
51. 第 231 行：f'{sheet_name}: Canola output exceeds 170 on {d}.；随行重复
52. 第 234 行：f'{sheet_name}: Wheat output exceeds 120 on {d}.；随行重复
53. 第 235 行：f'{sheet_name}: Canola output exceeds 120 on {d}.；随行重复
54. 第 237 行：f'{sheet_name}: Wheat output exceeds 135 on {d}.；随行重复
55. 第 238 行：f'{sheet_name}: Canola output exceeds 135 on {d}.；随行重复

### harbor_dc_recovery_01

断言 55 处，其中 22 处在循环内。源文件：Operational-Recovery-Planning/harbor_dc_recovery_01/tests/test_outputs.py

assert_formula_contains

1. 第 37 行：f'{cell_ref} must be a formula.
workbook

2. 第 113 行：f'Output workbook not found: {OUTPUT_XLSX}
due_map

3. 第 120 行：f'Reference workbook missing: {REFERENCE_XLSX}
summary_text

4. 第 127 行：f'Summary markdown not found: {OUTPUT_SUMMARY}
test_sheet_names

5. 第 132 行：set(workbook.sheetnames) == set(SHEET_NAMES)
test_sheet_layout_and_rules

6. 第 139 行：f'{sheet_name}: expected exactly {LAST_ROW} rows.
7. 第 141 行：ws['C2'].value == 'Rack-Mount Web Servers'
8. 第 142 行：ws['F2'].value == 'Blade Database Servers'
9. 第 143 行：ws['I2'].value == 'Network Appliances'
10. 第 157 行：f'{sheet_name}: header mismatch in C3:K3.
11. 第 160 行：f'{sheet_name}: B4 must be {START_DATE}.
extract_section

12. 第 290 行：f'Missing section header: ## Scenario {scenario_number}
test_summary_structure_and_required_statements

13. 第 313 行：Scenario 1 must contain 'May PO On-Time: No'.
14. 第 316 行：Scenario 2 must contain 'May PO On-Time: Web Yes, Database No'.
15. 第 321 行：Scenario 3 must contain 'May PO On-Time: Yes'.
16. 第 324 行：Scenario 3 must explicitly mention '30-day notification'.
assert_formula_contains

17. 第 39 行：f"{cell_ref} formula is missing token '{token}'. Got: {value}；随行重复
parse_nonnegative_int

18. 第 48 行：f'{cell_ref} must be a whole number.
19. 第 49 行：f'{cell_ref} must be nonnegative.
20. 第 53 行：f'{cell_ref} must be a numeric constant, not a formula.
21. 第 60 行：f'{cell_ref} must be a whole number.
22. 第 61 行：f'{cell_ref} must be nonnegative.
test_sheet_layout_and_rules

23. 第 204 行：f'{sheet_name}: wrong Web due on {d}. Expected {expected_a_due}, got {a_due}.；随行重复
24. 第 207 行：f'{sheet_name}: wrong Database due on {d}. Expected {expected_b_due}, got {b_due}.；随行重复
25. 第 255 行：f'{sheet_name}: total Network Appliances output must be >= 1200.
26. 第 256 行：f'{sheet_name}: expected Network Appliances to run on at least 10 days.
27. 第 257 行：f'{sheet_name}: Blade Database Servers production starts too early.
28. 第 260 行：f'{sheet_name}: expected both Web and Database backlogs to remain > 0 by May 1.
29. 第 265 行：f'{sheet_name}: must produce at least 100 Network Appliances units pre-relocation.
30. 第 266 行：f'{sheet_name}: Network Appliances output must be 0 on/after 2018-02-01.
31. 第 267 行：f'{sheet_name}: Blade Database Servers production starts too early.
32. 第 270 行：f'{sheet_name}: expected Web backlog cleared and Database backlog remaining by May 1.
33. 第 275 行：f'{sheet_name}: Network Appliances output must be zero for entire horizon.
34. 第 276 行：f'{sheet_name}: expected 20-24 high-output (10-hour shift) days, got {high_output_days}.
35. 第 279 行：f'{sheet_name}: Blade Database Servers production starts too early.
36. 第 282 行：f'{sheet_name}: expected both Web and Database backlogs cleared by May 1.
37. 第 212 行：f'{sheet_name}: Web production must be 0 on non-working day {d}.；随行重复
38. 第 213 行：f'{sheet_name}: Database production must be 0 on non-working day {d}.；随行重复
39. 第 214 行：f'{sheet_name}: Network Appliance production must be 0 on non-working day {d}.；随行重复
test_summary_structure_and_required_statements

40. 第 309 行：f"Scenario {idx} is missing required field '{label}'.；随行重复
test_sheet_layout_and_rules

41. 第 178 行：f'{sheet_name}: B{row} has incorrect date.；随行重复
42. 第 181 行：f'{sheet_name}: B{row} must be date or formula.；随行重复
43. 第 182 行：f'{sheet_name}: B{row} must advance date by 1 day.；随行重复
44. 第 218 行：f'{sheet_name}: Web output exceeds 120 on {d}.；随行重复
45. 第 219 行：f'{sheet_name}: Database output exceeds 120 on {d}.；随行重复
46. 第 221 行：f'{sheet_name}: Web output exceeds 135 on {d}.；随行重复
47. 第 222 行：f'{sheet_name}: Database output exceeds 135 on {d}.；随行重复
48. 第 226 行：f'{sheet_name}: 10-hour output used before 2018-02-01.；随行重复
49. 第 227 行：f'{sheet_name}: high-output day must be a working day ({d}).；随行重复
50. 第 230 行：f'{sheet_name}: Web output exceeds 170 on {d}.；随行重复
51. 第 231 行：f'{sheet_name}: Database output exceeds 170 on {d}.；随行重复
52. 第 234 行：f'{sheet_name}: Web output exceeds 120 on {d}.；随行重复
53. 第 235 行：f'{sheet_name}: Database output exceeds 120 on {d}.；随行重复
54. 第 237 行：f'{sheet_name}: Web output exceeds 135 on {d}.；随行重复
55. 第 238 行：f'{sheet_name}: Database output exceeds 135 on {d}.；随行重复

### harbor_gdpval_36

断言 28 处，其中 10 处在循环内。源文件：Operational-Recovery-Planning/harbor_gdpval_36/tests/test_outputs.py

load_reference_demands

1. 第 36 行：Missing 'Week' row in reference workbook
2. 第 37 行：Missing 'MIG weld Demand Total' row in reference workbook
load_plan_rows

3. 第 56 行：f'Output workbook missing: {PLAN_FILE}
4. 第 70 行：f'Header mismatch.\nExpected: {expected_headers}\nActual:   {actual_headers}
5. 第 88 行：f'Expected 49 weekly rows (weeks 4..52), found {len(rows)}
test_plan_math_and_policy

6. 第 107 行：Weeks must be continuous from 4 to 52 with no gaps
test_summary_file

7. 第 152 行：f'Summary file missing: {SUMMARY_FILE}
8. 第 160 行：Summary file must contain approximately 3 lines (2-4)
9. 第 164 行：Line 1 must match: First_Week_5_Days: <week-number-or-N/A>
10. 第 165 行：Line 2 must match: First_Week_4_Days: <week-number-or-N/A>
11. 第 171 行：f'First_Week_5_Days mismatch: expected {exp_5}, got {got_5}
12. 第 172 行：f'First_Week_4_Days mismatch: expected {exp_4}, got {got_4}
13. 第 174 行：Line 3 must start with 'Summary: 
14. 第 176 行：Summary text cannot be empty
15. 第 179 行：f'Summary exceeds 60 words ({len(words)})
16. 第 181 行：f'Summary exceeds 3 sentences ({sentence_count})
17. 第 184 行：Summary must mention the 5-day step-down week
18. 第 185 行：Summary must mention the 4-day step-down week
load_reference_demands

19. 第 51 行：f'Reference demand missing for week {week}；随行重复
test_plan_math_and_policy

20. 第 112 行：f'Week {week}: days must be one of 4/5/6；随行重复
21. 第 115 行：f'Week {week}: demand {demand} does not match reference {ref_demands[week]}；随行重复
22. 第 130 行：f'Week {week}: Start of Week Past Due should equal max(0, prior end)；随行重复
23. 第 135 行：f'Week {week}: capacity formula mismatch；随行重复
24. 第 137 行：f'Week {week}: end backlog formula mismatch；随行重复
25. 第 141 行：f'Week {week}: overtime formula mismatch；随行重复
26. 第 145 行：f'Week {week}: expected {exp_days} day(s), got {days}；随行重复
27. 第 121 行：Week 4 must satisfy Start of Week Past Due + Scheduled Demand = 438.81；随行重复
28. 第 127 行：f'Week {week}: calc carryover mismatch；随行重复

### harbor_gdpval_41

断言 55 处，其中 22 处在循环内。源文件：Operational-Recovery-Planning/harbor_gdpval_41/tests/test_outputs.py

assert_formula_contains

1. 第 37 行：f'{cell_ref} must be a formula.
workbook

2. 第 113 行：f'Output workbook not found: {OUTPUT_XLSX}
due_map

3. 第 120 行：f'Reference workbook missing: {REFERENCE_XLSX}
summary_text

4. 第 127 行：f'Summary markdown not found: {OUTPUT_SUMMARY}
test_sheet_names

5. 第 132 行：set(workbook.sheetnames) == set(SHEET_NAMES)
test_sheet_layout_and_rules

6. 第 139 行：f'{sheet_name}: expected exactly {LAST_ROW} rows.
7. 第 141 行：ws['C2'].value == 'Crew Cab Running Boards'
8. 第 142 行：ws['F2'].value == 'Extended Cab Running Boards'
9. 第 143 行：ws['I2'].value == 'Grill Guard'
10. 第 157 行：f'{sheet_name}: header mismatch in C3:K3.
11. 第 160 行：f'{sheet_name}: B4 must be {START_DATE}.
extract_section

12. 第 291 行：f'Missing section header: ## Scenario {scenario_number}
test_summary_structure_and_required_statements

13. 第 314 行：Scenario 1 must contain 'May PO On-Time: No'.
14. 第 317 行：Scenario 2 must contain 'May PO On-Time: Crew Yes, Extended No'.
15. 第 322 行：Scenario 3 must contain 'May PO On-Time: Yes'.
16. 第 325 行：Scenario 3 must explicitly mention '30-day notification'.
assert_formula_contains

17. 第 39 行：f"{cell_ref} formula is missing token '{token}'. Got: {value}；随行重复
parse_nonnegative_int

18. 第 48 行：f'{cell_ref} must be a whole number.
19. 第 49 行：f'{cell_ref} must be nonnegative.
20. 第 53 行：f'{cell_ref} must be a numeric constant, not a formula.
21. 第 60 行：f'{cell_ref} must be a whole number.
22. 第 61 行：f'{cell_ref} must be nonnegative.
test_sheet_layout_and_rules

23. 第 204 行：f'{sheet_name}: wrong Crew due on {d}. Expected {expected_crew_due}, got {crew_due}.；随行重复
24. 第 207 行：f'{sheet_name}: wrong Extended due on {d}. Expected {expected_ext_due}, got {ext_due}.；随行重复
25. 第 256 行：f'{sheet_name}: total Grill Guard output must be >= 1200.
26. 第 257 行：f'{sheet_name}: expected Grill Guard to run on at least 10 days.
27. 第 258 行：f'{sheet_name}: Extended production starts too early.
28. 第 261 行：f'{sheet_name}: expected both Crew and Extended backlogs to remain > 0 by May 1.
29. 第 266 行：f'{sheet_name}: must produce at least 100 Grill Guard units pre-relocation.
30. 第 267 行：f'{sheet_name}: Grill Guard output must be 0 on/after 2018-02-01.
31. 第 268 行：f'{sheet_name}: Extended production starts too early.
32. 第 271 行：f'{sheet_name}: expected Crew backlog cleared and Extended backlog remaining by May 1.
33. 第 276 行：f'{sheet_name}: Grill Guard output must be zero for entire horizon.
34. 第 277 行：f'{sheet_name}: expected 20-24 high-output (10-hour shift) days, got {high_output_days}.
35. 第 280 行：f'{sheet_name}: Extended production starts too early.
36. 第 283 行：f'{sheet_name}: expected both Crew and Extended backlogs cleared by May 1.
37. 第 212 行：f'{sheet_name}: Crew production must be 0 on non-working day {d}.；随行重复
38. 第 213 行：f'{sheet_name}: Extended production must be 0 on non-working day {d}.；随行重复
39. 第 214 行：f'{sheet_name}: Grill Guard production must be 0 on non-working day {d}.；随行重复
test_summary_structure_and_required_statements

40. 第 310 行：f"Scenario {idx} is missing required field '{label}'.；随行重复
test_sheet_layout_and_rules

41. 第 178 行：f'{sheet_name}: B{row} has incorrect date.；随行重复
42. 第 181 行：f'{sheet_name}: B{row} must be date or formula.；随行重复
43. 第 182 行：f'{sheet_name}: B{row} must advance date by 1 day.；随行重复
44. 第 219 行：f'{sheet_name}: Crew output exceeds 120 on {d}.；随行重复
45. 第 220 行：f'{sheet_name}: Extended output exceeds 120 on {d}.；随行重复
46. 第 222 行：f'{sheet_name}: Crew output exceeds 135 on {d}.；随行重复
47. 第 223 行：f'{sheet_name}: Extended output exceeds 135 on {d}.；随行重复
48. 第 227 行：f'{sheet_name}: 10-hour output used before 2018-02-01.；随行重复
49. 第 228 行：f'{sheet_name}: high-output day must be a working day ({d}).；随行重复
50. 第 231 行：f'{sheet_name}: Crew output exceeds 170 on {d}.；随行重复
51. 第 232 行：f'{sheet_name}: Extended output exceeds 170 on {d}.；随行重复
52. 第 235 行：f'{sheet_name}: Crew output exceeds 120 on {d}.；随行重复
53. 第 236 行：f'{sheet_name}: Extended output exceeds 120 on {d}.；随行重复
54. 第 238 行：f'{sheet_name}: Crew output exceeds 135 on {d}.；随行重复
55. 第 239 行：f'{sheet_name}: Extended output exceeds 135 on {d}.；随行重复

### harbor_wh_recovery_02

断言 55 处，其中 22 处在循环内。源文件：Operational-Recovery-Planning/harbor_wh_recovery_02/tests/test_outputs.py

assert_formula_contains

1. 第 37 行：f'{cell_ref} must be a formula.
workbook

2. 第 113 行：f'Output workbook not found: {OUTPUT_XLSX}
due_map

3. 第 120 行：f'Reference workbook missing: {REFERENCE_XLSX}
summary_text

4. 第 127 行：f'Summary markdown not found: {OUTPUT_SUMMARY}
test_sheet_names

5. 第 132 行：set(workbook.sheetnames) == set(SHEET_NAMES)
test_sheet_layout_and_rules

6. 第 139 行：f'{sheet_name}: expected exactly {LAST_ROW} rows.
7. 第 141 行：ws['C2'].value == 'Priority Express Orders'
8. 第 142 行：ws['F2'].value == 'Standard Freight Orders'
9. 第 143 行：ws['I2'].value == 'Bulk Pallet Loads'
10. 第 157 行：f'{sheet_name}: header mismatch in C3:K3.
11. 第 160 行：f'{sheet_name}: B4 must be {START_DATE}.
extract_section

12. 第 290 行：f'Missing section header: ## Scenario {scenario_number}
test_summary_structure_and_required_statements

13. 第 313 行：Scenario 1 must contain 'May PO On-Time: No'.
14. 第 316 行：Scenario 2 must contain 'May PO On-Time: Express Yes, Standard No'.
15. 第 321 行：Scenario 3 must contain 'May PO On-Time: Yes'.
16. 第 324 行：Scenario 3 must explicitly mention '30-day notification'.
assert_formula_contains

17. 第 39 行：f"{cell_ref} formula is missing token '{token}'. Got: {value}；随行重复
parse_nonnegative_int

18. 第 48 行：f'{cell_ref} must be a whole number.
19. 第 49 行：f'{cell_ref} must be nonnegative.
20. 第 53 行：f'{cell_ref} must be a numeric constant, not a formula.
21. 第 60 行：f'{cell_ref} must be a whole number.
22. 第 61 行：f'{cell_ref} must be nonnegative.
test_sheet_layout_and_rules

23. 第 204 行：f'{sheet_name}: wrong Express due on {d}. Expected {expected_a_due}, got {a_due}.；随行重复
24. 第 207 行：f'{sheet_name}: wrong Standard due on {d}. Expected {expected_b_due}, got {b_due}.；随行重复
25. 第 255 行：f'{sheet_name}: total Bulk Pallet Loads output must be >= 1200.
26. 第 256 行：f'{sheet_name}: expected Bulk Pallet Loads to run on at least 10 days.
27. 第 257 行：f'{sheet_name}: Standard Freight Orders production starts too early.
28. 第 260 行：f'{sheet_name}: expected both Express and Standard backlogs to remain > 0 by May 1.
29. 第 265 行：f'{sheet_name}: must produce at least 100 Bulk Pallet Loads units pre-relocation.
30. 第 266 行：f'{sheet_name}: Bulk Pallet Loads output must be 0 on/after 2018-02-01.
31. 第 267 行：f'{sheet_name}: Standard Freight Orders production starts too early.
32. 第 270 行：f'{sheet_name}: expected Express backlog cleared and Standard backlog remaining by May 1.
33. 第 275 行：f'{sheet_name}: Bulk Pallet Loads output must be zero for entire horizon.
34. 第 276 行：f'{sheet_name}: expected 20-24 high-output (10-hour shift) days, got {high_output_days}.
35. 第 279 行：f'{sheet_name}: Standard Freight Orders production starts too early.
36. 第 282 行：f'{sheet_name}: expected both Express and Standard backlogs cleared by May 1.
37. 第 212 行：f'{sheet_name}: Express production must be 0 on non-working day {d}.；随行重复
38. 第 213 行：f'{sheet_name}: Standard production must be 0 on non-working day {d}.；随行重复
39. 第 214 行：f'{sheet_name}: Bulk Pallet production must be 0 on non-working day {d}.；随行重复
test_summary_structure_and_required_statements

40. 第 309 行：f"Scenario {idx} is missing required field '{label}'.；随行重复
test_sheet_layout_and_rules

41. 第 178 行：f'{sheet_name}: B{row} has incorrect date.；随行重复
42. 第 181 行：f'{sheet_name}: B{row} must be date or formula.；随行重复
43. 第 182 行：f'{sheet_name}: B{row} must advance date by 1 day.；随行重复
44. 第 218 行：f'{sheet_name}: Express output exceeds 120 on {d}.；随行重复
45. 第 219 行：f'{sheet_name}: Standard output exceeds 120 on {d}.；随行重复
46. 第 221 行：f'{sheet_name}: Express output exceeds 135 on {d}.；随行重复
47. 第 222 行：f'{sheet_name}: Standard output exceeds 135 on {d}.；随行重复
48. 第 226 行：f'{sheet_name}: 10-hour output used before 2018-02-01.；随行重复
49. 第 227 行：f'{sheet_name}: high-output day must be a working day ({d}).；随行重复
50. 第 230 行：f'{sheet_name}: Express output exceeds 170 on {d}.；随行重复
51. 第 231 行：f'{sheet_name}: Standard output exceeds 170 on {d}.；随行重复
52. 第 234 行：f'{sheet_name}: Express output exceeds 120 on {d}.；随行重复
53. 第 235 行：f'{sheet_name}: Standard output exceeds 120 on {d}.；随行重复
54. 第 237 行：f'{sheet_name}: Express output exceeds 135 on {d}.；随行重复
55. 第 238 行：f'{sheet_name}: Standard output exceeds 135 on {d}.；随行重复

### new_task_1_soc_alert_recovery

断言 30 处，其中 11 处在循环内。源文件：Operational-Recovery-Planning/new_task_1_soc_alert_recovery/tests/test_outputs.py

load_reference_demands

1. 第 50 行：f"Missing week row '{cfg['input_week_label']}
2. 第 52 行：f'Missing demand row(s): {missing}
load_plan_rows

3. 第 71 行：f'Output workbook missing: {plan_file}
4. 第 73 行：f'Sheet names mismatch: {wb.sheetnames}
5. 第 76 行：f'Header mismatch: {headers}
6. 第 92 行：f'Expected {expected_count} rows, got {len(rows)}
test_plan_math_and_policy

7. 第 111 行：Weeks must be continuous and ordered.
8. 第 132 行：Plan should include at least one 4-day, 5-day, and 6-day week.
test_summary_file

9. 第 137 行：f'Summary file missing: {summary_file}
10. 第 146 行：Summary must contain approximately 3 lines (2-4).
11. 第 150 行：Line 1 must match First_Week_5_Days: <week-or-N/A>
12. 第 151 行：Line 2 must match First_Week_4_Days: <week-or-N/A>
13. 第 152 行：m5.group(1) == w5
14. 第 153 行：m4.group(1) == w4
15. 第 155 行：lines[2].startswith('Summary: ')
16. 第 158 行：f'Summary exceeds 60 words ({len(words)})
17. 第 159 行：Summary exceeds 3 sentences.
18. 第 160 行：Summary must mention 5-day week.
19. 第 161 行：Summary must mention 4-day week.
load_reference_demands

20. 第 65 行：f'Reference demand missing for week {w}；随行重复
test_plan_math_and_policy

21. 第 117 行：f'Week {week}: invalid days {days}；随行重复
22. 第 118 行：f'Week {week}: demand mismatch；随行重复
23. 第 123 行：abs(start_queue - max(0.0, calc_start)) <= 0.01；随行重复
24. 第 124 行：abs(capacity - CONFIG['rate_per_day'] * days) <= 0.01；随行重复
25. 第 126 行：abs(end_queue - expected_end) <= 0.01；随行重复
26. 第 128 行：abs(overtime - expected_ot) <= 0.01；随行重复
27. 第 129 行：days == expected_days(CONFIG, calc_start, demand)；随行重复
test_summary_file

28. 第 163 行：f'Summary must include phrase: {phrase}；随行重复
test_plan_math_and_policy

29. 第 120 行：abs(start_queue + demand - CONFIG['initial_total']) <= 0.01；随行重复
30. 第 122 行：abs(calc_start - prev_end) <= 0.01；随行重复

### new_task_2_radiology_reading_backlog

断言 30 处，其中 11 处在循环内。源文件：Operational-Recovery-Planning/new_task_2_radiology_reading_backlog/tests/test_outputs.py

load_reference_demands

1. 第 50 行：f"Missing week row '{cfg['input_week_label']}
2. 第 52 行：f'Missing demand row(s): {missing}
load_plan_rows

3. 第 71 行：f'Output workbook missing: {plan_file}
4. 第 73 行：f'Sheet names mismatch: {wb.sheetnames}
5. 第 76 行：f'Header mismatch: {headers}
6. 第 92 行：f'Expected {expected_count} rows, got {len(rows)}
test_plan_math_and_policy

7. 第 111 行：Weeks must be continuous and ordered.
8. 第 132 行：Plan should include at least one 4-day, 5-day, and 6-day week.
test_summary_file

9. 第 137 行：f'Summary file missing: {summary_file}
10. 第 146 行：Summary must contain approximately 3 lines (2-4).
11. 第 150 行：Line 1 must match First_Week_5_Days: <week-or-N/A>
12. 第 151 行：Line 2 must match First_Week_4_Days: <week-or-N/A>
13. 第 152 行：m5.group(1) == w5
14. 第 153 行：m4.group(1) == w4
15. 第 155 行：lines[2].startswith('Summary: ')
16. 第 158 行：f'Summary exceeds 60 words ({len(words)})
17. 第 159 行：Summary exceeds 3 sentences.
18. 第 160 行：Summary must mention 5-day week.
19. 第 161 行：Summary must mention 4-day week.
load_reference_demands

20. 第 65 行：f'Reference demand missing for week {w}；随行重复
test_plan_math_and_policy

21. 第 117 行：f'Week {week}: invalid days {days}；随行重复
22. 第 118 行：f'Week {week}: demand mismatch；随行重复
23. 第 123 行：abs(start_queue - max(0.0, calc_start)) <= 0.01；随行重复
24. 第 124 行：abs(capacity - CONFIG['rate_per_day'] * days) <= 0.01；随行重复
25. 第 126 行：abs(end_queue - expected_end) <= 0.01；随行重复
26. 第 128 行：abs(overtime - expected_ot) <= 0.01；随行重复
27. 第 129 行：days == expected_days(CONFIG, calc_start, demand)；随行重复
test_summary_file

28. 第 163 行：f'Summary must include phrase: {phrase}；随行重复
test_plan_math_and_policy

29. 第 120 行：abs(start_queue + demand - CONFIG['initial_total']) <= 0.01；随行重复
30. 第 122 行：abs(calc_start - prev_end) <= 0.01；随行重复

### new_task_3_returns_center_throughput

断言 30 处，其中 11 处在循环内。源文件：Operational-Recovery-Planning/new_task_3_returns_center_throughput/tests/test_outputs.py

load_reference_demands

1. 第 50 行：f"Missing week row '{cfg['input_week_label']}
2. 第 52 行：f'Missing demand row(s): {missing}
load_plan_rows

3. 第 71 行：f'Output workbook missing: {plan_file}
4. 第 73 行：f'Sheet names mismatch: {wb.sheetnames}
5. 第 76 行：f'Header mismatch: {headers}
6. 第 92 行：f'Expected {expected_count} rows, got {len(rows)}
test_plan_math_and_policy

7. 第 111 行：Weeks must be continuous and ordered.
8. 第 132 行：Plan should include at least one 4-day, 5-day, and 6-day week.
test_summary_file

9. 第 137 行：f'Summary file missing: {summary_file}
10. 第 146 行：Summary must contain approximately 3 lines (2-4).
11. 第 150 行：Line 1 must match First_Week_5_Days: <week-or-N/A>
12. 第 151 行：Line 2 must match First_Week_4_Days: <week-or-N/A>
13. 第 152 行：m5.group(1) == w5
14. 第 153 行：m4.group(1) == w4
15. 第 155 行：lines[2].startswith('Summary: ')
16. 第 158 行：f'Summary exceeds 60 words ({len(words)})
17. 第 159 行：Summary exceeds 3 sentences.
18. 第 160 行：Summary must mention 5-day week.
19. 第 161 行：Summary must mention 4-day week.
load_reference_demands

20. 第 65 行：f'Reference demand missing for week {w}；随行重复
test_plan_math_and_policy

21. 第 117 行：f'Week {week}: invalid days {days}；随行重复
22. 第 118 行：f'Week {week}: demand mismatch；随行重复
23. 第 123 行：abs(start_queue - max(0.0, calc_start)) <= 0.01；随行重复
24. 第 124 行：abs(capacity - CONFIG['rate_per_day'] * days) <= 0.01；随行重复
25. 第 126 行：abs(end_queue - expected_end) <= 0.01；随行重复
26. 第 128 行：abs(overtime - expected_ot) <= 0.01；随行重复
27. 第 129 行：days == expected_days(CONFIG, calc_start, demand)；随行重复
test_summary_file

28. 第 163 行：f'Summary must include phrase: {phrase}；随行重复
test_plan_math_and_policy

29. 第 120 行：abs(start_queue + demand - CONFIG['initial_total']) <= 0.01；随行重复
30. 第 122 行：abs(calc_start - prev_end) <= 0.01；随行重复

