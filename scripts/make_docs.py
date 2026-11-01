"""Write the storetrade documentation. Every number comes from outputs/reference_values.json (scripts/reference.py)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import re
N_QUERIES = len(list((ROOT / "powerquery").glob("*.m")))
N_MEASURES = len(re.findall(r"MEASURE _Measures\[", (ROOT / "powerbi" / "measures.dax").read_text()))
N_CHECKS = (ROOT / "powerbi" / "tests.dax").read_text().count('ROW ( "Check"')
V = {k: x["expected"] for k, x in json.load(open(ROOT / "outputs" / "reference_values.json")).items() if not k.startswith("_")}
n = lambda k: f"{V[k]:,.0f}"  # noqa: E731
usd = lambda k: f"${V[k]:,.2f}"  # noqa: E731
pct = lambda k: f"{V[k] * 100:.1f}%"  # noqa: E731


def w(path: str, text: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n")


# ------------------------------------------------------------------ README
w("README.md", f"""
# storetrade: store and category trading report in Power BI

A Power BI report on a year of real grocery transactions: how each store and department trades, how discounts move sales,
and whether the numbers can be trusted. It is built the way a retail reporting team would build one: Power Query to load and
clean, a star-schema model, DAX measures with written definitions, a reconciliation back to the source file, and technical
documentation for the next person.

**Data.** The Complete Journey, from 84.51° (the data arm of a US grocery retailer), via the `completejourney` R package:
{n('Loaded rows')} transaction lines, {n('Households')} households, {n('Stores')} stores, one year (2017), in US dollars. It is
American data from 2017, not UK data and not any UK retailer's. The raw files are not committed (the package page states no
licence; `scripts/export_raw.R` fetches them).

## Status

Built and tested in Power BI Desktop (2.149, November 2025) on Windows, 1 November 2026.

| | |
|---|---|
| Power Query ({N_QUERIES} queries in `powerquery/`) | Loads 1,469,307 transaction lines; every step is mirrored in SQL by `scripts/reference.py` |
| DAX (`powerbi/measures.dax`, {N_MEASURES} measures) | Loaded into the model from the template |
| Tests | `powerbi/tests.dax` in Desktop's DAX query view: **{N_CHECKS} of {N_CHECKS} checks PASS** against numbers computed independently in DuckDB, and the 3 blank-by-design checks are TRUE (`docs/img/tests_pass_44.jpg`, `docs/img/tests_blank_checks.jpg`) |
| Reconciliation | Rows and sales match `control_totals.csv` exactly (difference 0 and $0.00) |
| Report | 5 pages, 42 visuals: `storetrade.pbix` (data loaded) and `dist/storetrade.pbit` (template, no data) |

**Bug found in Desktop and fixed.** The first build ranked every store 1 and showed 0.0% against the store average:
`ALLSELECTED(Dim_Store[store_label])` misbehaves because `store_label` is sorted by `store_no`, so the sort column
stays in the filter context. The measures now use `ALLSELECTED(Dim_Store)` and the whole-table average, and return blank on totals.

Known cosmetic issues: the weekly charts scroll sideways (53 week labels); the data-quality cards show rounded
values (1M, $4.60M), and the exact figures are in the tests.

## Report pages

![Trading overview](docs/img/page1_trading_overview.jpg)
![Stores](docs/img/page2_stores.jpg)
![Departments](docs/img/page3_departments.jpg)
![Discounts](docs/img/page4_discounts.jpg)
![Data quality](docs/img/page5_data_quality.jpg)

## What the data says (reference run in DuckDB; Power BI returns the same numbers)

| | |
|---|---|
| Sales | {usd('Sales')} on {n('Baskets')} baskets: {usd('Avg Basket Value')} per basket |
| Discounts | {usd('Total Discount')} = {pct('Discount %')} of the {usd('Gross Sales')} shelf value (retail discount and retailer coupon match; manufacturer coupons, {usd('Manufacturer Coupon Value')}, are separate) |
| Petrol | {usd('Fuel Sales')} ({V['Fuel Sales'] / V['Sales'] * 100:.1f}% of sales) on {n('Fuel Lines')} lines whose "quantity" is not a unit count, so units and basket size exclude it |
| Private label | {pct('Private Label Share')} of non-fuel sales |
| Data quality | {n('Zero-Quantity Lines')} zero-quantity lines, {n('Free-Item Lines')} free items, {n('Unknown-Product Lines')} lines for products missing from the product file, no returns, no duplicates, 25 December absent |

## Repository

| Path | What |
|---|---|
| `scripts/export_raw.R` | Exports the data to CSV and writes `control_totals.csv` from the source object |
| `powerquery/*.m` | One file per query, in load order (see `docs/REFRESH.md`) |
| `powerbi/measures.dax` | Every measure, with comments |
| `powerbi/tests.dax` | Expected-versus-actual checks, generated from the reference run |
| `powerbi/REPORT_SPEC.md` | The five report pages, visual by visual |
| `scripts/reference.py` | Independent SQL mirror of every rule and measure; writes `outputs/reference_values.*` |
| `docs/BUILD_GUIDE.md` | Step-by-step build in Power BI Desktop, with checkpoints and fixes for common errors |
| `docs/` | Data model, data flow, business rules, data dictionary, data quality, refresh process |
| `tests/` | pytest: reference identities, and consistency between the M, DAX and test files |

## Honest limits

- US data, 2017, dollars. No store attributes exist (no region, size or format), so stores are compared with each other, not by region.
- `Gross Sales = sales_value + retail_disc + coupon_match_disc` assumes `sales_value` is net of those two discounts. The data
  supports it (shelf prices are more stable this way than with the alternative) but the package page does not define the
  fields, so it is an assumption, stated in `docs/BUSINESS_RULES.md`.
- Households are a sample of frequent shoppers, so household measures describe loyal customers, not all customers.
- Week 1 is one day (Sunday 1 January) and 25 December has no transactions: week-on-week skips the first and per-day
  measures use trading days.
""")

# ------------------------------------------------------------------ DATA_MODEL
w("docs/DATA_MODEL.md", f"""
# Data model (technical specification)

Import mode, one fact table and three dimensions (a star). Household is not a dimension: the extract has an id and nothing
else about households, so `household_id` stays on the fact and is counted with DISTINCTCOUNT.

```mermaid
erDiagram
    Dim_Date ||--o{{ Fact_Sales : "Date"
    Dim_Store ||--o{{ Fact_Sales : "store_id"
    Dim_Product ||--o{{ Fact_Sales : "product_id"
    Recon_Control {{ int expected_rows }}
    DQ_Rules {{ text RuleID }}
```

| Table | Grain | Rows | Source |
|---|---|---|---|
| Fact_Sales | one transaction line | {n('Loaded rows')} | `transactions.csv` |
| Dim_Product | one product | {n('Dim_Product rows')} (92,331 from the file + {V['Dim_Product rows'] - 92331:.0f} unknown) | `products.csv` + keys found on sales lines |
| Dim_Store | one store | {n('Dim_Store rows')} | distinct `store_id` on sales lines |
| Dim_Date | one calendar day | {n('Dim_Date rows')} | generated from `Param_StartDate` to `Param_EndDate` |
| Recon_Control | one row | 1 | `control_totals.csv` (written before Power BI) |
| DQ_Rules | one rule | 8 | generated by `scripts/reference.py` |
| _Measures | none | 0 | holds the measures |

## Relationships

| From (many) | To (one) | Cardinality | Filter direction | Active |
|---|---|---|---|---|
| Fact_Sales[product_id] | Dim_Product[product_id] | many to one | single | yes |
| Fact_Sales[store_id] | Dim_Store[store_id] | many to one | single | yes |
| Fact_Sales[Date] | Dim_Date[Date] | many to one | single | yes |

`Recon_Control` and `DQ_Rules` are disconnected on purpose: they are reference tables, not filters. Referential integrity was
checked in the reference run: orphan product keys {n('Orphan product keys')}, store keys {n('Orphan store keys')}, date keys {n('Orphan date keys')}.

## Model settings

- Mark `Dim_Date` as the date table on `[Date]`.
- Sort: `Dim_Store[store_label]` by `store_no`; `Dim_Date[Month]` by `MonthNo`; `Dim_Date[WeekLabel]` by `WeekNo`; `Dim_Date[DayName]` by `DayNo`.
- Hide: every key and flag column on `Fact_Sales`, `store_id`, `store_no`, `WeekNo`, `MonthNo`, `DayNo`, and the `_Measures` placeholder column.
- Summarization "Don't summarize" on all columns (measures do the aggregating); `Fact_Sales[sales_value]` and the other money columns are Fixed decimal.
- Display folders for measures: Sales and discounts; Baskets and units; Mix and ranking; Time; Data quality; Reconciliation.
- Row-level security: none (no personal data; households are numeric ids; no names, addresses or card numbers exist in the extract).

## Performance notes

- `Transactions_Raw` is read three times (fact, product keys, store keys), so the first load reads the 110 MB CSV three times (a minute or two).
- `Source Week Mismatch Lines` scans every line: use it on the Data Quality page only.
- `Fact_Sales[transaction_timestamp]` is kept for an hour-of-day analysis; remove it to shrink the model if you do not use it.
""")

# ------------------------------------------------------------------ DATA_FLOW
w("docs/DATA_FLOW.md", """
# Data flow

```mermaid
flowchart LR
    A[completejourney package<br/>84.51°, US grocer, 2017] -->|scripts/export_raw.R| B[transactions.csv<br/>products.csv]
    A -->|same script, from the source object| C[control_totals.csv]
    B --> D[Transactions_Raw<br/>types only, no rows changed]
    B --> P[Products_Raw<br/>types only]
    P --> E[Dim_Product<br/>+ unknown products, IsFuel]
    D --> E
    D --> F[Fact_Sales<br/>Date, shelf_value, line_flag]
    D --> G[Dim_Store]
    H[Param_StartDate/EndDate<br/>Ref_ClosedDates] --> I[Dim_Date]
    C --> J[Recon_Control]
    F & E & G & I --> K[Semantic model<br/>3 relationships, measures]
    J --> K
    L[DQ_Rules<br/>generated] --> K
    K --> M[Report: 5 pages]
    K -->|powerbi/tests.dax| N[Expected vs actual<br/>from scripts/reference.py]
```

| Step | What happens | Rows in → out | Where |
|---|---|---|---|
| Export | Source object written to CSV; control totals taken from the source | 1,469,307 → 1,469,307 | `scripts/export_raw.R` |
| Transactions_Raw | Read, text keys, money as fixed decimal, timestamp parsed. Nothing removed | 1,469,307 → 1,469,307 | `powerquery/Transactions_Raw.m` |
| Fact_Sales | Adds Date, shelf_value, line_flag; renames week to source_week | 1,469,307 → 1,469,307 | `powerquery/Fact_Sales.m` |
| Products_Raw | Read products.csv, set types (staging, not loaded) | 92,331 → 92,331 | `powerquery/Products_Raw.m` |
| Dim_Product | Products_Raw + products on sales lines but not in the file; IsFuel. Reads no file itself (avoids the Formula.Firewall) | 92,331 + 17 | `powerquery/Dim_Product.m` |
| Dim_Store | Distinct store ids | 457 | `powerquery/Dim_Store.m` |
| Dim_Date | One row per day; Monday-start weeks matching the source; partial and closed flags | 365 | `powerquery/Dim_Date.m` |
| Reconcile | Model rows and sales compared with `control_totals.csv` | difference must be 0 | Reconciliation page; `tests.dax` |

No line is deleted anywhere in the flow. Issues are flagged or handled in a dimension, so the report always reconciles to the
source (rows, sales value) and every treatment is a visible rule (`docs/BUSINESS_RULES.md`).
""")

# ------------------------------------------------------------------ BUSINESS_RULES
w("docs/BUSINESS_RULES.md", f"""
# Business rules and reporting logic

All amounts are US dollars. "Non-fuel" means `Dim_Product[IsFuel] = FALSE`.

## Export rules (applied by `scripts/export_raw.R`, before Power BI)

| Rule | Finding | Treatment |
|---|---|---|
| E1 | 28 money cells carry floating-point residue (largest 1.8e-15), which R writes in scientific notation | Money rounded to whole cents; every real value already was, so totals are unchanged |
| E2 | Quantity stored as a decimal type | Written as a whole number (all quantities are whole) |
| E3 | Timestamps carry the America/New_York time zone | Written as local store time, not converted to UTC, so dates match the source's weeks |

## Data rules (each is a row in `DQ_Rules`, shown on the Data Quality page)

| Rule | Finding | Lines | Sales | Treatment |
|---|---|---|---|---|
| DQ01 | Quantity = 0 | {n('Zero-Quantity Lines')} | {usd('Zero-Quantity Sales')} | Kept. The value counts in Sales; the line adds no units. `line_flag = Zero quantity` |
| DQ02 | Quantity > 0 and sales_value = 0 | {n('Free-Item Lines')} | $0.00 | Kept. Promotional give-aways. `line_flag = Free item` |
| DQ03 | Petrol: "quantity" is not a unit count (up to 89,638 on one line) | {n('Fuel Lines')} | {usd('Fuel Sales')} | Kept in Sales and Fuel Sales; excluded from Units, Items per Basket, Avg Selling Price |
| DQ04 | Product missing from the product file | {n('Unknown-Product Lines')} | {usd('Unknown-Product Sales')} | Kept; department UNKNOWN (17 products) |
| DQ05 | Negative values | {n('Negative value lines')} | | None found; returns are not modelled |
| DQ06 | Exact duplicate lines | {n('Exact duplicate lines')} | | None found |
| DQ07 | Calendar day with no transactions | {n('Days with no sales (calendar)')} day | | 25 December. `IsClosed`; Sales per Trading Day excludes it |
| DQ08 | Source `week` differs from `Dim_Date[WeekNo]` | {n('Source week mismatch lines')} | | None; weeks are Monday-start and week 1 is 1 January alone, so `IsPartialWeek` is true for week 1 only |

## Measure definitions

| Measure | Definition | Format |
|---|---|---|
| Sales | Sum of `sales_value`: what the retailer received after discounts | $#,##0 |
| Gross Sales | Sum of `shelf_value` = `sales_value + retail_disc + coupon_match_disc`: the value at shelf price. **Assumes `sales_value` is net of those discounts** | $#,##0 |
| Retail Discount, Coupon Match Discount | Sums of `retail_disc`, `coupon_match_disc` (stored as positive amounts) | $#,##0 |
| Total Discount | Retail Discount + Coupon Match Discount | $#,##0 |
| Discount % | Total Discount ÷ Gross Sales | 0.0% |
| Manufacturer Coupon Value | Sum of `coupon_disc`. Funded by manufacturers, so not part of Discount % | $#,##0 |
| Baskets | Distinct `basket_id` | #,##0 |
| Households | Distinct `household_id` (a sample of frequent shoppers) | #,##0 |
| Units | Sum of `quantity`, non-fuel only | #,##0 |
| Sales ex Fuel, Fuel Sales | Sales with `IsFuel` false, true | $#,##0 |
| Avg Basket Value | Sales ÷ Baskets (petrol included in both) | $0.00 |
| Items per Basket | Units ÷ baskets that contain at least one non-fuel line | 0.0 |
| Avg Selling Price | Sales ex Fuel ÷ Units | $0.00 |
| Private Label Share | Non-fuel sales where `brand = Private` ÷ Sales ex Fuel | 0.0% |
| Share of Total Sales | Sales ÷ Sales with every product filter removed | 0.0% |
| Share of Department Sales | Sales ÷ Sales with category and type filters removed (category share inside a department) | 0.0% |
| Store Rank | RANKX over the stores in the current selection, descending, dense | 0 |
| Sales vs Store Avg % | Sales ÷ average Sales of the stores in the current selection, minus 1 | +0.0%;-0.0% |
| Sales per Trading Day | Sales ÷ days in the selection that are not `IsClosed` | $#,##0 |
| Sales PW | Sales of the previous week number; blank unless the previous week is a full week (week 2 has none) | $#,##0 |
| Sales WoW % | (Sales − Sales PW) ÷ Sales PW; blank where Sales PW is blank | +0.0%;-0.0% |
| Rolling 4 Week Sales | Sales of the selected week and the three before it, full weeks only; blank until four full weeks exist (first value: week 5) | $#,##0 |
| Loaded Rows (all), Sales (all) | Rows and sales in the model ignoring every slicer | #,##0 |
| Control Rows, Control Sales | From `control_totals.csv` | #,##0 |
| Row Difference, Sales Difference | Loaded minus control; **must be 0** | #,##0 |

Reading week-on-week: week 53 has six trading days (Christmas Day is closed), so a week-52 to week-53 change is partly
calendar. Use Sales per Trading Day to compare them.
""")

# ------------------------------------------------------------------ DATA_DICTIONARY
rows = [
    ("Fact_Sales", "Date", "transactions.csv: transaction_timestamp", "date", "Store-local date of the line. Timestamps are local store time as stored in the source; they are not converted to UTC", "Date key"),
    ("Fact_Sales", "transaction_timestamp", "transaction_timestamp", "datetime", "Local store time of the line", "Optional"),
    ("Fact_Sales", "basket_id", "basket_id", "text", "One shopping trip: one household, one store, one day", "No basket spans stores or households"),
    ("Fact_Sales", "household_id", "household_id", "text", "Loyalty-card household", "2,469 households, frequent shoppers"),
    ("Fact_Sales", "store_id", "store_id", "text", "Store", "Text key; no attributes available"),
    ("Fact_Sales", "product_id", "product_id", "text", "Product", "17 ids missing from the product file"),
    ("Fact_Sales", "quantity", "quantity", "decimal", "Units sold", "Not units for petrol (DQ03)"),
    ("Fact_Sales", "sales_value", "sales_value", "fixed decimal", "Amount the retailer received for the line", ""),
    ("Fact_Sales", "retail_disc", "retail_disc", "fixed decimal", "Retailer loyalty-card discount, positive amount", ""),
    ("Fact_Sales", "coupon_match_disc", "coupon_match_disc", "fixed decimal", "Retailer match of a manufacturer coupon, positive amount", ""),
    ("Fact_Sales", "coupon_disc", "coupon_disc", "fixed decimal", "Manufacturer coupon value", "Not retailer-funded"),
    ("Fact_Sales", "shelf_value", "derived", "fixed decimal", "sales_value + retail_disc + coupon_match_disc", "Assumption: see BUSINESS_RULES"),
    ("Fact_Sales", "line_flag", "derived", "text", "Sale, Free item, Zero quantity", "DQ01, DQ02"),
    ("Fact_Sales", "source_week", "week", "whole number", "Week number in the source", "Reconciled to Dim_Date[WeekNo] (DQ08)"),
    ("Dim_Product", "product_id", "products.csv", "text", "Key", "+17 unknown products"),
    ("Dim_Product", "manufacturer_id", "manufacturer_id", "text", "Manufacturer", ""),
    ("Dim_Product", "department", "department", "text", "Department (31 values incl. UNKNOWN)", ""),
    ("Dim_Product", "brand", "brand", "text", "National, Private, or Unknown", "Private = own label"),
    ("Dim_Product", "product_category / product_type / package_size", "same", "text", "Category, type, size", "Blank where the source is blank"),
    ("Dim_Product", "IsFuel", "derived", "true/false", "product_type starts with GASOLINE", "DQ03"),
    ("Dim_Store", "store_id / store_no / store_label", "derived", "text / whole / text", "Key, numeric order, label", "Sort label by store_no"),
    ("Dim_Date", "Date, Year, MonthNo, Month, DayNo, DayName, IsWeekend", "generated", "", "Calendar columns (Monday = 1)", ""),
    ("Dim_Date", "WeekNo, WeekStart, WeekLabel", "generated", "", "Source-compatible Monday-start weeks; week 1 = 1 January", "DQ08"),
    ("Dim_Date", "IsPartialWeek", "generated", "true/false", "True for week 1", "Skipped by WoW and rolling measures"),
    ("Dim_Date", "IsClosed", "Ref_ClosedDates", "true/false", "True for 25 December", "DQ07"),
]
body = "\n".join(f"| {a} | {b} | {c} | {d} | {e} | {f} |" for a, b, c, d, e, f in rows)
w("docs/DATA_DICTIONARY.md", f"""
# Data dictionary and mapping (source to model)

| Table | Column | Source | Type | Meaning | Note |
|---|---|---|---|---|---|
{body}
""")

# ------------------------------------------------------------------ REFRESH / PROCESS
w("docs/REFRESH.md", f"""
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
""")

# ------------------------------------------------------------------ REPORT_SPEC
w("powerbi/REPORT_SPEC.md", f"""
# Report specification: five pages

Theme: one accent colour for the measure being read, grey for context; US dollars; every visual has a title that states the
question it answers and alt text. Slicers sync across pages 1 to 4: Month, Department, Fuel (`Dim_Product[IsFuel]`, default
"all", so totals match Sales).

## 1. Trading overview: how is the year trading?
- Cards: Sales ({usd('Sales')}), Discount % ({pct('Discount %')}), Baskets ({n('Baskets')}), Avg Basket Value ({usd('Avg Basket Value')}), Items per Basket ({V['Items per Basket']:.1f}), Private Label Share ({pct('Private Label Share')}).
- Line and column: Sales by `WeekLabel` (columns) with Rolling 4 Week Sales (line). Tooltip page: Sales WoW %, Sales per Trading Day.
- Column: Sales by day of week (`DayName`). Text note: week 1 is one day; 25 December is closed.

## 2. Stores: which stores lead and lag?
- Table of stores: Store Rank, Sales, Sales vs Store Avg %, Baskets, Avg Basket Value, Discount %, with data bars on Sales and
  conditional icons on Sales vs Store Avg %. Top N filter on Store Rank (default 25).
- Bar: top 15 stores by Sales. Scatter: Baskets (x) against Avg Basket Value (y), size Sales, detail store.
- Note: no store attributes exist in the data, so no region or format cuts.

## 3. Departments and categories: what sells, and at what price?
- Matrix: Department > Category with Sales, Share of Department Sales, Discount %, Avg Selling Price (expand with drill).
- Treemap: Sales by Department. Bar: Private Label Share by Department.
- Drillthrough page target: Department (from pages 1 and 2) showing weekly Sales and the top 10 categories.

## 4. Discounts and coupons: where do discounts go?
- Column: Discount % by Department (non-fuel). Line: Discount % by `WeekLabel`.
- Stacked bar: Retail Discount against Coupon Match Discount by Department. Card: Manufacturer Coupon Value, labelled "funded by manufacturers, not in Discount %".

## 5. Data quality and reconciliation: can the numbers be trusted?
- Cards: Row Difference and Sales Difference (both 0, red if not); Loaded Rows (all) beside Control Rows; Sales (all) beside Control Sales.
- Table from `DQ_Rules`: RuleID, Check, Treatment, ExpectedCount, Actual (DQ rule), with a flag when they differ.
- Text: the three assumptions (gross sales definition; US 2017 data; households are frequent shoppers).

## Interactions and checks
- Cross-filtering on, except cards on page 5 (edit interactions off). Bookmarks: "All sales", "Excluding fuel".
- Tab order set per page (View > Selection > Tab order); colours chosen for contrast; no information carried by colour alone.
- After building, run `powerbi/tests.dax` again with a Month slicer cleared: results must not change (the tests run unfiltered).
""")
print("docs written")
