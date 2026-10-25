Use the filing data in `/root/2025-q2` and `/root/2025-q3` together with `/root/alerts_input.json` to create `/root/answers.json`.

`alerts_input.json` contains a mixed alert feed. Some entries are duplicates, and some entries are distractors that must be ignored.

Produce a JSON object with exactly these top-level keys:

```json
{
  "issuer_top_holders": [
    {
      "issuer_query": "",
      "quarter": "",
      "manager_names": ["", "", ""]
    }
  ],
  "fund_change": [
    {
      "fund_query_current": "",
      "quarter_current": "",
      "fund_query_baseline": "",
      "quarter_baseline": "",
      "largest_buy_cusip": ""
    }
  ]
}
```

Requirements:
- Process only alert objects whose `type` is `issuer_top_holders` or `fund_change`.
- Ignore every other alert type.
- Deduplicate alerts within each type by their semantic content, not by object position.
- Preserve the first-seen order of distinct alerts within each type.
- For `issuer_top_holders`, resolve the issuer query to one stock CUSIP, then return the top 3 Q3 manager names by aggregated VALUE for that CUSIP.
- For `fund_change`, resolve the fund query separately in Q2 and Q3, compare stock-like holdings only, and return the single CUSIP with the largest positive VALUE change.
- Write only the JSON file requested.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q2`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
