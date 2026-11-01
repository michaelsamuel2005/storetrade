# Data dictionary and mapping (source to model)

| Table | Column | Source | Type | Meaning | Note |
|---|---|---|---|---|---|
| Fact_Sales | Date | transactions.csv: transaction_timestamp | date | Store-local date of the line. Timestamps are local store time as stored in the source; they are not converted to UTC | Date key |
| Fact_Sales | transaction_timestamp | transaction_timestamp | datetime | Local store time of the line | Optional |
| Fact_Sales | basket_id | basket_id | text | One shopping trip: one household, one store, one day | No basket spans stores or households |
| Fact_Sales | household_id | household_id | text | Loyalty-card household | 2,469 households, frequent shoppers |
| Fact_Sales | store_id | store_id | text | Store | Text key; no attributes available |
| Fact_Sales | product_id | product_id | text | Product | 17 ids missing from the product file |
| Fact_Sales | quantity | quantity | decimal | Units sold | Not units for petrol (DQ03) |
| Fact_Sales | sales_value | sales_value | fixed decimal | Amount the retailer received for the line |  |
| Fact_Sales | retail_disc | retail_disc | fixed decimal | Retailer loyalty-card discount, positive amount |  |
| Fact_Sales | coupon_match_disc | coupon_match_disc | fixed decimal | Retailer match of a manufacturer coupon, positive amount |  |
| Fact_Sales | coupon_disc | coupon_disc | fixed decimal | Manufacturer coupon value | Not retailer-funded |
| Fact_Sales | shelf_value | derived | fixed decimal | sales_value + retail_disc + coupon_match_disc | Assumption: see BUSINESS_RULES |
| Fact_Sales | line_flag | derived | text | Sale, Free item, Zero quantity | DQ01, DQ02 |
| Fact_Sales | source_week | week | whole number | Week number in the source | Reconciled to Dim_Date[WeekNo] (DQ08) |
| Dim_Product | product_id | products.csv | text | Key | +17 unknown products |
| Dim_Product | manufacturer_id | manufacturer_id | text | Manufacturer |  |
| Dim_Product | department | department | text | Department (31 values incl. UNKNOWN) |  |
| Dim_Product | brand | brand | text | National, Private, or Unknown | Private = own label |
| Dim_Product | product_category / product_type / package_size | same | text | Category, type, size | Blank where the source is blank |
| Dim_Product | IsFuel | derived | true/false | product_type starts with GASOLINE | DQ03 |
| Dim_Store | store_id / store_no / store_label | derived | text / whole / text | Key, numeric order, label | Sort label by store_no |
| Dim_Date | Date, Year, MonthNo, Month, DayNo, DayName, IsWeekend | generated |  | Calendar columns (Monday = 1) |  |
| Dim_Date | WeekNo, WeekStart, WeekLabel | generated |  | Source-compatible Monday-start weeks; week 1 = 1 January | DQ08 |
| Dim_Date | IsPartialWeek | generated | true/false | True for week 1 | Skipped by WoW and rolling measures |
| Dim_Date | IsClosed | Ref_ClosedDates | true/false | True for 25 December | DQ07 |
