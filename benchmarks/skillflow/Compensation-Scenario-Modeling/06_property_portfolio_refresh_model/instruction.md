Build a multi-year Excel compensation workbook for a property operations team.

Output:

`/root/Portfolio_Services_Compensation.xlsx`

Inputs:

1. `/root/asset_register_packet.xlsx`
2. `/root/operations_roster_packet.xlsx`

Both source packets include a `Packet Notes` worksheet. Those note tabs are context only and must not appear in the final workbook.

Required workbook contract:

1. The workbook must contain exactly these worksheets (in this order):
   - `Summary`
   - `Assumptions`
   - `Building Specs`
   - `Roster`
   - `Calculations --->`
   - `EE Calcs (Current)`
   - `EE Calcs (Yr+1)`
   - `EE Calcs (Yr+2)`

2. Read both source files and preserve their working data in the final workbook:
   - asset / building data in `Building Specs`
   - staff data in `Roster`

3. Keep the standard 3-year property compensation structure:
   - quarterly totals row 91 in each EE Calcs sheet
   - summary rows for base pay, property bonus, occupancy incentive, portfolio fee, vehicle allowance, health insurance, retirement match, total, and Y/Y growth
   - formula-linked summary references to EE Calcs totals

4. Define the property assumption named ranges across all 3 years.

Only the final workbook path above is graded.

## Refresh layout specification (2026-10-13)

Summary B1 must read `Harborfront Portfolio Services - Staff Compensation`. C5 holds the source base salary assumption (numeric); D5 must use the Excel formula `=C5*1.03`. Define at least 46 meaningful assumption named ranges across the three years.

Keep the source roster in output Roster starting at row 5; employee names must occupy column B. EE Calcs employee rows start at row 4 with names in column B. Column F stores numeric service years from the input roster; Yr+1 advances Current by one year and Yr+2 advances it by two years. Department, rank and other text must occupy separate columns.

Totals are row 91 in each EE Calcs sheet, including H91. Summary total row 33 links the corresponding quarterly calculation-sheet totals at row 91, including C33, D33 and E33.
