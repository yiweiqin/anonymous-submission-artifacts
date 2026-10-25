You are the Cloud Capacity Operations Lead at Nimbus Compute.

            Build an Excel workbook at:
            - `/root/Nimbus_Capacity_Reconciliation_4-25.xlsx`

            Use these normalized input files:
            - `/root/compute_capacity_schedule_input.csv`
            - `/root/storage_capacity_schedule_input.csv`
            - `/root/capacity_ledger_balances.json`

            For operational context only, source documents are also present:
            - `/root/Nimbus_Compute_Reservation_Register_Q1Q2_2025.txt`
- `/root/Nimbus_Storage_Commitment_Register_Q1Q2_2025.txt`
- `/root/nimbus_platform_ledger_notes_apr25.txt`

            Create exactly three sheets in this order:
            1. `Capacity Summary`
            2. `Compute Pool #8100`
            3. `Storage Pool #8200`

            Keep the same row/column structure, control rows, and formula rules as the reference Harbor reconciliation task:
            - line items start at row 6
            - control rows: `Month Totals`, `Ending Balance`, `Variance`, `GL Balance`
            - summary formulas in B7/B8/B9/B12/B13/B14/B16 link to column O of the two detail tabs
            - B16 must be `B9+B14`

            Important:
            - Keep numeric values numeric (not text).
            - Do not change source files.
            - Final deliverable must be one `.xlsx` workbook at the required path.

## Reconciliation layout specification (2026-10-13)

All sheets: A1 = `Nimbus Compute`. Detail sheets: A2 must contain the account number named in the sheet title. Summary: A2 must contain `Summary`, A3 must contain `4/30/2025`, A5 = `Description`, B5 = `Amount`.

Copy CSV rows in their original order starting at row 6, with these column mappings:

- A: `vendor` (text).
- B: `beginning_balance` (numeric).
- C: `jan_adds` (numeric).
- D: `jan_amortization` (numeric).
- E: `jan_ending_balance` (numeric).
- F: `feb_adds` (numeric).
- G: `feb_amortization` (numeric).
- H: `feb_ending_balance` (numeric).
- I: `mar_adds` (numeric).
- J: `mar_amortization` (numeric).
- K: `mar_ending_balance` (numeric).
- L: `apr_adds` (numeric).
- M: `apr_amortization` (numeric).
- N: `apr_ending_balance` (numeric).
- O: `amortization_months` (numeric).
- P: `comments` (text).
- Q: `account_number` (numeric).

Let s=6, e=5+the number of input rows, t=e+1, u=t+1, v=t+2 and g=t+3. Label column A at these four rows Month Totals, Ending Balance, Variance and GL Balance respectively.

- At t: each B:N cell sums its own column from s through e; O is Ct+Ft+It+Lt.
- At u: E=Bt+Ct-Dt; H=Et+Ft-Gt; K=Ht+It-Jt; N=Kt+Lt-Mt; O=Dt+Gt+Jt+Mt.
- At g: E/H/K/N contain the respective Jan/Feb/Mar/Apr balances from the matching ledger JSON account; O=Ot-Ou.
- At v: O=Og-Ng.
- Summary B7/B8/B9 link to the first detail sheet's O cells at t/u/g; B12/B13/B14 link to the second detail sheet's O cells at t/u/g. B16=B9+B14.

Use actual Excel formulas at these addresses, substituting row numbers and quoting sheet names in cross-sheet references. These requirements specify the previously referenced reconciliation layout; derive all amounts from supplied inputs.
