Build a multi-year Excel compensation workbook for a university's full-time faculty.

Output:

`/root/Faculty_Termload_Compensation.xlsx`

Input:

`/root/faculty_termload_packet.xlsx`

The source packet includes an extra `Packet Notes` sheet. Ignore it in the final output.

Workbook contract:

1. Keep exactly these 7 worksheets in order:
   - `Summary`
   - `Assumptions`
   - `Roster`
   - `Calculations --->`
   - `EE Calcs (Current)`
   - `EE Calcs (Yr+1)`
   - `EE Calcs (Yr+2)`

2. Preserve the standard faculty modeling structure:
   - assumptions migrated into `Assumptions`
   - faculty roster migrated into `Roster`
   - quarterly totals on row 79 of each EE Calcs sheet

3. `Summary` must still include these 8 compensation components:
   - Base Pay (9-Month)
   - Summer Session Pay
   - Sabbatical Bonus
   - Department Stipend
   - Media Rights Allocation
   - Health Insurance
   - Retirement Match
   - TOTAL and Y/Y Growth rows

4. Define the faculty assumption named ranges across all 3 years.

5. Keep the year-projection behavior:
   - projected sheets advance service years
   - summary totals remain cross-sheet linked
   - total and Y/Y rows remain formula-based

Only the final workbook path above is graded.

## Output contract clarification (2026-10-13)

In each EE Calcs sheet, column E must store numeric years of service for each faculty data row, sourced from the input roster's years-of-service column; department or rank text must be stored elsewhere. Store the calculated numeric service years in this column: Yr+1 is Current plus one year and Yr+2 is Current plus two years. Keep quarterly component groups in H through AI and preserve the required quarterly SUM totals. Summary B1 must retain the requested organization name.

## Refresh layout specification (2026-10-13)

Summary B1 must read `Lakeshore State University - Faculty Compensation`. C5 holds the source base salary assumption (numeric); D5 must use the Excel formula `=C5*1.03`. Define at least 50 meaningful assumption named ranges across the three years.

Keep the source roster in output Roster starting at row 5; employee names must occupy column B. EE Calcs employee rows start at row 4 with names in column B. Column E stores numeric service years from the input roster; Yr+1 advances Current by one year and Yr+2 advances it by two years. Department, rank and other text must occupy separate columns.

Use the standard faculty quarter groups H:K base pay, L:O summer session, P:S sabbatical, T:W department stipend, X:AA media, AB:AE health and AF:AI retirement. Totals are row 79. Summary rows 26:32 hold those seven components; row 33 is their total and row 34 is YoY growth.
