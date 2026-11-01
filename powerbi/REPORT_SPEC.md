# Report specification: five pages

Theme: one accent colour for the measure being read, grey for context; US dollars; every visual has a title that states the
question it answers and alt text. Slicers sync across pages 1 to 4: Month, Department, Fuel (`Dim_Product[IsFuel]`, default
"all", so totals match Sales).

## 1. Trading overview: how is the year trading?
- Cards: Sales ($4,596,039.58), Discount % (14.8%), Baskets (155,848), Avg Basket Value ($29.49), Items per Basket (13.4), Private Label Share (21.7%).
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
