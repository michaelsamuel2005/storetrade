// Query: Fact_Sales   (Enable load: on). One row per transaction line: 1,469,307 rows, none removed (reconciled to control_totals.csv).
// Adds: Date (store-local date), shelf_value (value before discounts), line_flag (rules DQ01 and DQ02).
// Rule DQ03 (petrol quantity) and DQ04 (unknown product) are handled in Dim_Product, not by deleting lines.
let
    Source = Transactions_Raw,
    AddDate = Table.AddColumn(Source, "Date", each DateTime.Date([transaction_timestamp]), type date),
    // shelf_value = what the lines would have cost with no retail or coupon-match discount. Assumption, see docs/BUSINESS_RULES.md:
    // sales_value is net of retail_disc and coupon_match_disc. coupon_disc is manufacturer-funded and is not added back.
    AddShelf = Table.AddColumn(AddDate, "shelf_value", each [sales_value] + [retail_disc] + [coupon_match_disc], Currency.Type),
    AddFlag = Table.AddColumn(
        AddShelf, "line_flag",
        each if [quantity] = 0 then "Zero quantity" else if [sales_value] = 0 then "Free item" else "Sale",
        type text
    ),
    Renamed = Table.RenameColumns(AddFlag, {{"week", "source_week"}}),
    Ordered = Table.ReorderColumns(
        Renamed,
        {"Date", "transaction_timestamp", "basket_id", "household_id", "store_id", "product_id", "quantity",
         "sales_value", "retail_disc", "coupon_match_disc", "coupon_disc", "shelf_value", "line_flag", "source_week"}
    )
in
    Ordered
