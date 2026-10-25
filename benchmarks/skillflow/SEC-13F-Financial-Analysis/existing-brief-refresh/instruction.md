Update the existing JSON report at `/root/brief_template.json` and save the completed result as `/root/answers.json`.

Use the filing data in `/root/2025-q2` and `/root/2025-q3` to fill in the placeholder values while preserving the existing structure and any untouched content.

The final JSON must keep the same top-level keys, section order, item order, and notes array as the template.

Fill the report as follows:
- Set `report_date` to `2025-q3`.
- In section `fund_snapshots`, for `renaissance technologies` and `scion asset management`, resolve each manager in Q3 and fill `aum` with total VALUE across the filing and `stock_holdings` with the count of stock-like rows.
- In section `issuer_leaders`, for `palantir` and `meta platforms`, resolve each issuer to one stock CUSIP and fill `top_manager` with the Q3 manager name having the highest aggregated VALUE for that CUSIP.
- In section `change_checks`, for `bridgewater associates` and `third point`, resolve each manager separately in Q2 and Q3, compare stock-like holdings by CUSIP, and fill `largest_buy_cusip` and `largest_sell_cusip`.
- Preserve the existing `notes` content exactly.

Write only the completed JSON report to `/root/answers.json`.

## Filing selection conventions (2026-10-13)

For this task, stock-like rows are those whose lowercased TITLEOFCLASS is exactly one of the following labels:

`adr`, `cap stk cl a`, `cap stk cl c`, `cl a`, `cl a com`, `cl a new`, `cl b`, `cl b new`, `class a`, `class a com`, `cmn`, `com`, `com cl a`, `com new`, `com shs`, `comm stk`, `common`, `common stock`, `equity`, `foreign stock`, `ord shs`, `shs cl a`, `sponsored adr`, `sponsored adrs`, `sponsored ads`, `stock`.

This is the legacy class-list convention for these tasks; fund-snapshot-canonical has its own explicitly stated substring definition and is a separate contract.

Manager matching uses RapidFuzz WRatio on the query and original FILINGMANAGER_NAME strings, without a processor; choose the first source-order name on ties. For that manager, prefer the first non-amendment cover-page row (ISAMENDMENT=N); if none, use its first row. Match independently in each requested quarter.

For issuer identity, use stock-like rows from `2025-q2`. Deduplicate CUSIP in source order, lowercase NAMEOFISSUER and query, choose the highest WRatio match without a processor, breaking ties by source order. Then use the identified CUSIP against the requested holdings quarter.

VALUE changes and top holdings are aggregated by CUSIP. Break equal VALUE or change ranks by ascending CUSIP; top-manager VALUE ties by ascending ACCESSION_NUMBER. All amounts must be computed from the input data.
