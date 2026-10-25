Create `/root/answers.json` from the filing data in `/root/2025-q2` and `/root/2025-q3`.

The JSON file must have exactly this structure:

```json
{
  "comparison_pairs": [
    {
      "fund_query_current": "third point",
      "quarter_current": "2025-q3",
      "fund_query_baseline": "third point",
      "quarter_baseline": "2025-q2",
      "largest_buy_cusip": "",
      "largest_sell_cusip": ""
    },
    {
      "fund_query_current": "tiger global",
      "quarter_current": "2025-q3",
      "fund_query_baseline": "tiger global",
      "quarter_baseline": "2025-q2",
      "largest_buy_cusip": "",
      "largest_sell_cusip": ""
    }
  ],
  "issuer_checks": [
    {
      "issuer_query": "microsoft",
      "quarter": "2025-q3",
      "top2_manager_names": ["", ""]
    },
    {
      "issuer_query": "meta platforms",
      "quarter": "2025-q3",
      "top2_manager_names": ["", ""]
    }
  ],
  "snapshot_check": {
    "fund_query": "scion asset management",
    "quarter": "2025-q3",
    "stock_holdings": 0
  }
}
```

Requirements:
- For each object in `comparison_pairs`, resolve the manager query separately in each quarter using the closest filing manager name from that quarter's cover page data.
- For each comparison pair, compare stock-like holdings only, aggregate by CUSIP within each quarter, and return the single CUSIP with the largest positive VALUE change as `largest_buy_cusip` and the single CUSIP with the most negative VALUE change as `largest_sell_cusip`.
- For each object in `issuer_checks`, resolve the issuer query to one stock CUSIP, then rank Q3 managers by descending aggregated VALUE for that CUSIP and return the top 2 manager names in order.
- For `snapshot_check`, resolve the manager query in Q3 and return the number of stock-like holding rows for that filing.
- Keep the array order and quarter labels exactly as shown.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q2`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
