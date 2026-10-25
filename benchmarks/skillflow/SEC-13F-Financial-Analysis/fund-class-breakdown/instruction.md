Create `/root/answers.json` using the Q3 filing data in `/root/2025-q3`.

Use the manager name query `elliott associates` to resolve the correct filing manager in the Q3 cover page data. Then compute a class breakdown for that filing.

Return a JSON object with exactly this schema:

```json
{
  "fund_query": "elliott associates",
  "quarter": "2025-q3",
  "aum_total": 0,
  "stock_row_count": 0,
  "stock_cusip_count": 0,
  "top_class_labels": ["", "", "", ""],
  "top_class_counts": [0, 0, 0, 0]
}
```

Requirements:
- `aum_total` is the total VALUE across all rows in the matched filing.
- Treat stock-like rows the same way throughout the task family.
- `stock_row_count` is the number of stock-like rows in the filing.
- `stock_cusip_count` is the number of distinct stock CUSIPs after grouping those stock-like rows by CUSIP.
- `top_class_labels` and `top_class_counts` must describe the 4 most frequent normalized stock-like `TITLEOFCLASS` labels within the filing.
- Normalize `TITLEOFCLASS` by lowercasing before counting.
- Order the class breakdown by descending count, breaking ties by ascending normalized label.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q3`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
