Create `/root/answers.json` for an issuer ownership rollup using the 13F data in `/root/2025-q2` and `/root/2025-q3`.

Use the issuer name query `palantir` to identify the correct stock CUSIP. Match the closest issuer name from the available stock rows, then use that CUSIP against the Q3 holdings data.

Return a JSON object with exactly this schema:

```json
{
  "issuer_query": "palantir",
  "quarter": "2025-q3",
  "cusip": "",
  "top5_managers": ["", "", "", "", ""],
  "top5_accessions": ["", "", "", "", ""]
}
```

Requirements:
- Resolve the issuer query to one CUSIP first.
- In Q3, aggregate VALUE by ACCESSION_NUMBER for that CUSIP.
- Rank managers by descending aggregated VALUE for that CUSIP.
- `top5_managers` and `top5_accessions` must refer to the same ranked rows in the same order.
- Manager names must come from the Q3 cover page data.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q2`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
