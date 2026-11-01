# Process descriptions: build from scratch, refresh, check

## Build from scratch (Windows, Power BI Desktop)

1. **Data (any machine with R).** `Rscript scripts/export_raw.R data` writes `transactions.csv`, `products.csv` and
   `control_totals.csv` to `data/`. Copy the folder to the Windows machine (about 118 MB; zips to about a fifth of that).
2. **Parameters.** Home > Transform data > Manage parameters > New: `Param_DataFolder` (Text, your folder with a trailing
   backslash), `Param_StartDate` (Date, 2017-01-01), `Param_EndDate` (Date, 2017-12-31). Or paste `Param_*.m` into blank queries.
3. **Queries, in this order** (Home > New source > Blank query > Advanced editor > paste, then rename to the file's name):
   `Ref_ClosedDates`, `Transactions_Raw`, `Products_Raw`, `Fact_Sales`, `Dim_Product`, `Dim_Store`, `Dim_Date`, `Recon_Control`, `DQ_Rules`.
   Right-click `Transactions_Raw`, `Products_Raw` and `Ref_ClosedDates`, untick **Enable load**. Close & Apply (a minute or two).
   Before the first refresh: File > Options and settings > Options > Current File > Privacy > Ignore the Privacy Levels (local files only).
4. **Model.** Create the three relationships and the settings in `docs/DATA_MODEL.md`; mark `Dim_Date` as the date table.
5. **Measures.** Enter data: a blank table named `_Measures`. DAX query view: paste `powerbi/measures.dax`, Run, then
   "Update model: add new measure" for each (or "Update model with changes"). Set formats from `docs/BUSINESS_RULES.md`.
6. **Test.** DAX query view: paste `powerbi/tests.dax`, Run. Every row must say PASS, and the second query must return TRUE, TRUE.
   If a row fails, fix the cause (do not edit the expected value): `outputs/reference_values.md` lists what each number is.
7. **Report.** Build the five pages from `powerbi/REPORT_SPEC.md`. Add alt text to every visual.
8. **Save as a Power BI project** (File > Save as > Power BI project, `.pbip`) so the model and report are text files in Git;
   `.gitignore` keeps the data cache out. Take screenshots into `docs/img/`.

## Refresh

1. Replace the CSVs (re-run the export) and refresh. If `control_totals.csv` changed, update `Param_StartDate/EndDate` and
   `Ref_ClosedDates` (any calendar day with no transactions).
2. Open the Data Quality page: Row Difference and Sales Difference must be 0, and each DQ rule's Actual must equal Expected
   (or be explained). If `scripts/reference.py` is re-run on the new data, `DQ_Rules.m` and `tests.dax` regenerate.

## Check the pipeline without Power BI

`python3 scripts/reference.py data && python3 -m pytest -q`. This recomputes every number independently and checks that the
Power Query, DAX and test files agree with each other.
