Create `/root/answers.json` from the filing data in `/root/2025-q3`.

Build a manager-versus-issuer grid for two manager queries and two issuer queries.

Return a JSON object with exactly this shape:

```json
{
  "manager_issuer_grid": [
    {
      "fund_query": "bridgewater associates",
      "quarter": "2025-q3",
      "issuer_queries": [
        {"issuer_query": "amazon", "cusip": "", "value": 0},
        {"issuer_query": "palantir", "cusip": "", "value": 0}
      ]
    },
    {
      "fund_query": "third point",
      "quarter": "2025-q3",
      "issuer_queries": [
        {"issuer_query": "amazon", "cusip": "", "value": 0},
        {"issuer_query": "palantir", "cusip": "", "value": 0}
      ]
    }
  ]
}
```

Requirements:
- Resolve each manager query against the Q3 cover page data.
- Resolve each issuer query to one stock CUSIP.
- For each manager and issuer pair, sum VALUE across all Q3 rows in that filing for the resolved CUSIP.
- Keep the manager order and issuer order exactly as shown.
- Use numeric values, not strings.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q3`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
