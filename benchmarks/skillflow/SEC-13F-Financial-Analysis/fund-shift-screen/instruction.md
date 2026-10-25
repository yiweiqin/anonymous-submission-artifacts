Prepare `/root/answers.json` by comparing one manager's stock holdings between `/root/2025-q2` and `/root/2025-q3`.

Use the manager name query `bridgewater associates` in each quarter separately. For each quarter, match the closest filing manager name in that quarter's cover page data, then use the accession number from that quarter.

Return a JSON object with exactly this schema:

```json
{
  "fund_query_current": "bridgewater associates",
  "quarter_current": "2025-q3",
  "fund_query_baseline": "bridgewater associates",
  "quarter_baseline": "2025-q2",
  "top4_increased_cusips": ["", "", "", ""],
  "top3_decreased_cusips": ["", "", ""],
  "new_positions_top2": ["", ""]
}
```

Requirements:
- Compare stock-like holdings only.
- Aggregate by CUSIP within each quarter before comparing.
- `top4_increased_cusips` must contain the 4 CUSIPs with the largest positive VALUE change from Q2 to Q3, ordered from largest increase to smaller increase.
- `top3_decreased_cusips` must contain the 3 CUSIPs with the most negative VALUE change, ordered from largest decrease to smaller decrease.
- `new_positions_top2` must contain the first 2 CUSIPs that were absent in Q2 and present in Q3, ordered by descending positive VALUE change.
- Use the quarter labels exactly as shown.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q2`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
