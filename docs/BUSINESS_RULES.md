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
| DQ01 | Quantity = 0 | 8,869 | $12.52 | Kept. The value counts in Sales; the line adds no units. `line_flag = Zero quantity` |
| DQ02 | Quantity > 0 and sales_value = 0 | 2,406 | $0.00 | Kept. Promotional give-aways. `line_flag = Free item` |
| DQ03 | Petrol: "quantity" is not a unit count (up to 89,638 on one line) | 14,697 | $384,044.07 | Kept in Sales and Fuel Sales; excluded from Units, Items per Basket, Avg Selling Price |
| DQ04 | Product missing from the product file | 4,836 | $172.57 | Kept; department UNKNOWN (17 products) |
| DQ05 | Negative values | 0 | | None found; returns are not modelled |
| DQ06 | Exact duplicate lines | 0 | | None found |
| DQ07 | Calendar day with no transactions | 1 day | | 25 December. `IsClosed`; Sales per Trading Day excludes it |
| DQ08 | Source `week` differs from `Dim_Date[WeekNo]` | 0 | | None; weeks are Monday-start and week 1 is 1 January alone, so `IsPartialWeek` is true for week 1 only |

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
