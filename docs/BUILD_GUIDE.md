# storetrade: complete build guide for Power BI Desktop (Windows)

What you will have at the end: a Power BI report (`storetrade.pbix` and a `.pbip` project), 44 of 44 tests passing,
five report pages, a PDF export and screenshots, all copied off the laptop.

## Time plan

| Part | What | Time |
|---|---|---|
| 0 | Files, folders, install | 15 min |
| 1 | Settings | 2 min |
| 2 | Parameters | 5 min |
| 3 | Queries | 30 min |
| 4 | Load and first save | 5 min |
| 5 | Model | 15 min |
| 6 | Measures and formats | 20 min |
| 7 | Tests (the checkpoint) | 10 min |
| 8 | Report pages | 2 to 3 hours |
| 9 | Final checks | 10 min |
| 10 | Save, export, take home, clean up | 20 min |

Parts 0 to 7 are the core (about 1.5 hours). If time is short, finish those, save, and build the pages later.

## Four rules

1. **Don't edit the M or DAX code.** If something errors, take a screenshot (Windows key + Shift + S) and send it to me.
2. **Names must match exactly**, capitals and underscores included: the queries refer to each other by name.
3. **Save often** (Ctrl + S) once the file is saved in part 4.
4. **Work in order.** The tests in part 7 must pass before you build pages.

---

## Part 0. Files, folders, install (15 minutes)

1. In the chat, download **storetrade_project.zip** and **storetrade_data_v2.zip**. Don't use the first data zip
   (it has 28 values Power Query could misread).
2. Open File Explorer > This PC > Local Disk (C:). Create a folder `storetrade`. Inside it create `project` and `data`.
3. Right-click storetrade_project.zip > Extract All > browse to `C:\storetrade\project` > Extract.
   Check: `C:\storetrade\project\powerquery` holds 12 files ending in `.m`.
4. Right-click storetrade_data_v2.zip > Extract All > `C:\storetrade\data` > Extract.
   Check: `C:\storetrade\data` holds `transactions.csv` (about 110 MB), `products.csv` and `control_totals.csv`, directly
   in that folder, not in a subfolder.
5. Open the Microsoft Store app > search **Power BI Desktop** > Get. When it opens, close the sign-in window. No account
   is needed for anything in this guide.
6. Only if Power BI won't install or crashes: Settings > System > About. If "System type" says ARM-based processor, run
   Windows Update first (Power BI needs the September 2025 update or later on ARM).

## Part 1. Settings (2 minutes)

1. In Power BI Desktop: **File > Options and settings > Options**.
2. Left side, under **CURRENT FILE**, click **Privacy** > select **Ignore the Privacy Levels and potentially improve
   performance**. (Both sources are your local CSVs; this prevents "Formula.Firewall" errors.)
3. Under **CURRENT FILE**, click **Data Load** > in "Time intelligence", untick **Auto date/time**. Leave
   "Autodetect new relationships after data is loaded" ticked.
4. Click **OK**.

## Part 2. Parameters (5 minutes)

1. Home ribbon > **Transform data**. The Power Query Editor opens in a new window.
2. Home > **Manage Parameters** > **New Parameter**. A dialog opens.
3. Create the first parameter:
   - Name: `Param_DataFolder`
   - Required: ticked
   - Type: **Text**
   - Suggested Values: Any value
   - Current Value: `C:\storetrade\data\` (the backslash at the end matters)
4. In the same dialog click **New** (top left) and create:
   - Name: `Param_StartDate`, Required ticked, Type: **Date** (not Date/Time), Current Value: 1 January 2017
     (type `01/01/2017`).
5. Click **New** again:
   - Name: `Param_EndDate`, Required ticked, Type: **Date**, Current Value: 31 December 2017. On a UK-format laptop
     type `31/12/2017`; on a US-format laptop `12/31/2017`.
6. Click **OK**. Click `Param_EndDate` in the Queries list on the left and check it reads 31 December 2017.

## Part 3. Queries (30 minutes)

You'll add nine queries, one per file, in this order:

| # | File in `C:\storetrade\project\powerquery\` | Enable load | What it does |
|---|---|---|---|
| 1 | `Ref_ClosedDates.m` | **off** | The one closed day (25 December) |
| 2 | `Transactions_Raw.m` | **off** | Reads transactions.csv, sets types |
| 3 | `Products_Raw.m` | **off** | Reads products.csv, sets types |
| 4 | `Fact_Sales.m` | on | Sales lines plus Date, shelf_value, line_flag |
| 5 | `Dim_Product.m` | on | Products plus the 17 unknown ones, IsFuel |
| 6 | `Dim_Store.m` | on | The 457 stores |
| 7 | `Dim_Date.m` | on | One row per day of 2017 |
| 8 | `Recon_Control.m` | on | Control totals from the export |
| 9 | `DQ_Rules.m` | on | The data-quality rule table |

Skip the three `Param_*.m` files: you made the parameters in part 2.

**For each file, do these five steps:**

1. Home > **New Source** > **Blank Query**. A query called Query1 appears in the list.
2. Home > **Advanced Editor**. Select everything in the box (Ctrl + A) and delete it.
3. In File Explorer, right-click the `.m` file > Open with > **Notepad**. Ctrl + A, Ctrl + C.
4. Back in the Advanced Editor, Ctrl + V, then click **Done**.
5. Rename the query: right-click it in the Queries list > **Rename** > type the file name without `.m`
   (for example `Transactions_Raw`) > Enter.

If you see "The name '…' wasn't recognized" right after pasting, check the spelling of the query names; it clears once
the query it refers to exists with the right name.

**Turn off loading for the three staging queries:** right-click `Ref_ClosedDates` > untick **Enable load**. Do the same
for `Transactions_Raw` and `Products_Raw`. Their names turn italic.

**Check each query** by clicking it and looking at the preview. The bottom-left corner shows columns and rows.

| Query | What you should see |
|---|---|
| `Transactions_Raw` | 11 columns. First row: household_id 900, store_id 330, quantity 1, sales_value 0.5, transaction_timestamp 01/01/2017 06:53:26 |
| `Products_Raw` | 7 columns. First row: product_id 25671, GROCERY, National, FRZN ICE |
| `Fact_Sales` | 14 columns starting Date, transaction_timestamp, basket_id. First row: Date 01/01/2017, sales_value 0.5, shelf_value 0.5, line_flag Sale |
| `Dim_Product` | 8 columns; last one IsFuel showing TRUE or FALSE. Takes 20 to 40 seconds (it reads the transactions too) |
| `Dim_Store` | 3 columns: store_id, store_no, store_label ("Store 2" style labels), 457 rows |
| `Dim_Date` | 12 columns, 365 rows. First row: 01/01/2017, Jan, WeekNo 1, W01, DayName Sun, IsPartialWeek TRUE |
| `Recon_Control` | 1 row; expected_rows 1469307, expected_sales_value 4,596,039.58 |
| `DQ_Rules` | 8 rows, DQ01 to DQ08 |

No query should show a yellow warning bar or the word Error in any cell. If one does, screenshot it and send it to me.

## Part 4. Load and first save (5 minutes)

1. Home > **Close & Apply** (top left). A Load window lists each table with a row count. Expect about 1 to 3 minutes.
   Checkpoint: Fact_Sales 1,469,307 rows; Dim_Product 92,348; Dim_Store 457; Dim_Date 365.
2. If the window reports errors, screenshot it and stop.
3. **File > Save as** > browse to `C:\storetrade\project` > name `storetrade` > Save. From now on press Ctrl + S after
   every part.

## Part 5. Model (15 minutes)

**Relationships**

1. Click **Model view** on the far left (the icon with three linked boxes).
2. Home > **Manage relationships**. You need exactly these three, each Active, cardinality **Many to one (\*:1)**,
   cross-filter direction **Single**:

   | From table and column | To table and column |
   |---|---|
   | Fact_Sales, `product_id` | Dim_Product, `product_id` |
   | Fact_Sales, `store_id` | Dim_Store, `store_id` |
   | Fact_Sales, `Date` | Dim_Date, `Date` |

3. Power BI has probably created all three. For any that is missing: **New relationship** > choose the tables and columns
   above > Cardinality Many to one > Cross filter direction Single > tick "Make this relationship active" > Save/OK.
4. Delete any other relationship (select it > Delete). Close the dialog.

**Date table**

5. Click the Dim_Date table > **Table tools** ribbon > **Mark as date table** > switch it on > choose the `Date` column >
   Save/OK. Power BI checks that the dates are unique and continuous; this passes with 365 days.

**Sort by column** (makes labels sort in the right order)

6. Click **Table view** on the far left (the grid icon). In the Data pane on the right, expand Dim_Store and click the
   `store_label` column > **Column tools** ribbon > **Sort by column** > `store_no`.
7. Repeat for Dim_Date:
   - `Month` sorted by `MonthNo`
   - `WeekLabel` sorted by `WeekNo`
   - `DayName` sorted by `DayNo`

**Summarization** (stops Power BI adding up numbers that are labels)

8. Still in Table view, click each of these and set **Column tools > Summarization** to **Don't summarize**:
   `Dim_Date[Year]`, `Dim_Date[MonthNo]`, `Dim_Date[WeekNo]`, `Dim_Date[DayNo]`, `Dim_Store[store_no]`,
   `DQ_Rules[ExpectedCount]`, `DQ_Rules[ExpectedSales]`.

**Hide technical columns** (they still work inside the measures)

9. In the Data pane, right-click each column below > **Hide in report view**:
   - Fact_Sales: every column **except** `line_flag`
   - Dim_Store: `store_id`, `store_no`
   - Dim_Date: `MonthNo`, `WeekNo`, `DayNo`
10. Ctrl + S.

## Part 6. Measures and formats (20 minutes)

**Create the measures table**

1. Click **Report view** (far left, top icon). Home > **Enter data**.
2. Type `_Measures` in the **Name** box at the bottom. Don't type anything in the grid. Click **Load**.

**Add the 45 measures**

3. Click **DAX query view** on the far left (the icon with DAX on it).
4. Open `C:\storetrade\project\powerbi\measures.dax` in Notepad, Ctrl + A, Ctrl + C, and paste it into the query editor.
5. Click **Run** (or press F5). Result: one row, `defined` = 1. If you see an error, screenshot it and send it to me.
6. Click **Update model with changes** in the command bar at the top. All 45 measures are written into `_Measures`.
7. Go back to Report view. In the Data pane, expand `_Measures`, right-click `Column1` > **Hide in report view**.
   `_Measures` now holds only measures and may jump to the top of the list with a calculator icon.

**Formats** (fast way: format several measures at once)

8. Click **Model view**. In the Data pane, hold Ctrl and click every measure in one row of the table below. In the
   **Properties** pane, open **Formatting** and set the format. Then do the next row.

| Measures | Format |
|---|---|
| Sales, Gross Sales, Retail Discount, Coupon Match Discount, Total Discount, Manufacturer Coupon Value, Sales ex Fuel, Fuel Sales, Sales per Trading Day, Sales PW, Rolling 4 Week Sales | Currency, **$ English (United States)**, 0 decimal places |
| Avg Basket Value, Avg Selling Price, Zero-Quantity Sales, Unknown-Product Sales, Sales (all), Control Sales, Sales Difference | Currency, $ English (United States), 2 decimal places |
| Discount %, Private Label Share, Share of Total Sales, Share of Department Sales, Sales WoW %, Sales vs Store Avg % | Percentage, 1 decimal place |
| Items per Basket | Decimal number, 1 decimal place |
| Baskets, Households, Units, Store Rank, Zero-Quantity Lines, Free-Item Lines, Fuel Lines, Unknown-Product Lines, Source Week Mismatch Lines, Loaded Rows (all), Control Rows, Row Difference, Actual (DQ rule) | Whole number, thousands separator on |

9. Optional but tidy: with the same multi-selection, type a **Display folder** in Properties: `1 Sales and discounts`,
   `2 Baskets and units`, `3 Mix and ranking`, `4 Time`, `5 Data quality`, `6 Reconciliation` (the groups follow the
   comments in measures.dax).
10. Ctrl + S.

## Part 7. Tests (10 minutes): the checkpoint

1. Click **DAX query view**. Click **+** at the bottom to open a new query tab.
2. Open `C:\storetrade\project\powerbi\tests.dax` in Notepad, copy all, paste, **Run**.
3. **Result 1** must show **44 rows, every one PASS** in the Result column. Rows that fail sort to the top, so a glance
   at the first row tells you.
4. **Result 2** (switch to it at the top of the results area) must show **True, True**.
5. Take a screenshot showing the results and save it as `C:\storetrade\project\docs\img\tests_pass.png` (create the
   `img` folder).
6. If any row says FAIL: don't change anything. Screenshot it and send it to me.

## Part 8. Report pages (2 to 3 hours)

**How to do the basic moves** (you'll repeat these):

- **Add a visual:** click an empty spot on the canvas, then click the visual's icon in the **Visualizations** pane. Drag
  fields from the **Data** pane into the boxes ("wells") named below.
- **Move and resize:** drag the visual's edge; drag a corner to resize.
- **Title:** select the visual > **Format visual** (paintbrush icon) > **General** > **Title** > Text.
- **Alt text** (for screen readers): Format visual > General > **Alt text**. One sentence on what it shows.
- **Sort:** hover the visual > **…** (More options) > **Sort axis** > choose the field, then Sort ascending/descending.
- **Rename a page:** double-click its tab at the bottom. **New page:** the **+** next to the tabs.
- **Visual filter:** select the visual > **Filters** pane > "Filters on this visual" > drag a field in.

Optional look: **View** > **Themes** > pick one with good contrast. Keep one accent colour.

### Page 1: Trading overview

Rename "Page 1" to `Trading overview`.

1. **Heading:** Insert > **Text box** at the top: `storetrade · store and category trading, 2017 (US grocery data, US$)`.
2. **Three slicers** across the top. For each: Slicer visual > drag the field into **Field** > Format visual > Visual >
   **Slicer settings** > Options > Style: **Dropdown** > set the Title.
   - `Dim_Date[Month]`, title "Month"
   - `Dim_Product[department]`, title "Department"
   - `Dim_Product[IsFuel]`, title "Petrol lines (True = petrol)"
3. **Six cards** in a row. For each: **Card** visual > drag the measure into **Fields**. (If you see both "Card" and
   "Card (new)", either works.)

   | Card | Should show with no slicer selected |
   |---|---|
   | Sales | $4,596,040 |
   | Discount % | 14.8% |
   | Baskets | 155,848 |
   | Avg Basket Value | $29.49 |
   | Items per Basket | 13.4 |
   | Private Label Share | 21.7% |

4. **Weekly trend:** **Line and clustered column chart**.
   - X-axis: `Dim_Date[WeekLabel]`
   - Column y-axis: `Sales`
   - Line y-axis: `Rolling 4 Week Sales`
   - Tooltips: `Sales WoW %`, `Sales per Trading Day`
   - Sort axis by WeekLabel, ascending (W01 to W53).
   - Title: "How are weekly sales trending? Bars: week; line: last four full weeks"
   - Check: W01 is a tiny bar ($10,478: one day only), W02 is $93,370, the line starts at W05, W53 dips to $80,829
     (Christmas Day closed).
5. **Weekday pattern:** **Clustered column chart**.
   - X-axis: `Dim_Date[DayName]`; Y-axis: `Sales per Trading Day`
   - Sort axis by DayName, ascending (Mon to Sun).
   - Title: "Which days trade best? Sales per trading day"
   - Check: Sun about $15,498 and Sat about $14,878 are highest; Wed about $10,824 lowest.
6. **Note:** a small text box at the bottom: "Week 1 is a single day (Sunday 1 January). 25 December has no
   transactions. Petrol counts in Sales but not in units or items per basket."
7. Add alt text to every visual. Ctrl + S.

### Page 2: Stores

New page, rename `Stores`.

1. **Ranking table:** **Table** visual. Columns, in this order: `Dim_Store[store_label]`, `Store Rank`, `Sales`,
   `Sales vs Store Avg %`, `Baskets`, `Avg Basket Value`, `Discount %`.
   - Sort: … > Sort by > Store Rank > Sort ascending.
   - Filters pane > Filters on this visual > `Store Rank` > "Show items when the value" **is less than or equal to** `25`
     > **Apply filter**.
   - Format visual > Visual > **Cell elements** > Series: `Sales` > **Data bars** on. Series: `Sales vs Store Avg %` >
     **Icons** on.
   - Title: "Which stores lead? Top 25 by sales"
   - Check: row 1 is Store 367, rank 1, $148,170; then Store 406 ($120,904) and Store 429 ($86,884).
   - Don't be alarmed that Sales vs Store Avg % shows over +1,000% at the top: many stores have only a handful of
     households in this sample, so the average store is small.
2. **Top 15 bar chart:** **Clustered bar chart**. Y-axis `store_label`, X-axis `Sales`.
   - Filters on this visual > `store_label` > Filter type **Top N** > Show items **Top** `15` > By value: drag `Sales` >
     **Apply filter**.
   - Sort axis by Sales, descending. Title: "Top 15 stores by sales".
3. **Traffic versus basket size:** **Scatter chart**. Values: `store_label`; X-axis: `Baskets`; Y-axis:
   `Avg Basket Value`; Size: `Sales`. Title: "Do stores win on visits or on basket size?"
4. Alt text on each. Ctrl + S.

### Page 3: Departments and categories

New page, rename `Departments`.

1. **Matrix:** **Matrix** visual.
   - Rows: `Dim_Product[department]`, then `Dim_Product[product_category]` underneath it in the same well.
   - Values: `Sales`, `Share of Total Sales`, `Share of Department Sales`, `Discount %`, `Avg Selling Price`.
   - Click the column header **Sales** to sort descending.
   - Use the forked-arrow icon above the visual (**Expand all down one level**) to show categories.
   - Title: "What sells, and at what price?"
   - Check: GROCERY first with $2,316,394 and 50.4% share of total. FUEL shows no Avg Selling Price; that's by design
     (petrol quantities aren't units).
2. **Treemap:** Category `department`, Values `Sales`. Title "Share of sales by department".
3. **Private label bar chart:** **Clustered bar chart**. Y-axis `department`, X-axis `Private Label Share`.
   - Filters on this visual: `department` > Basic filtering > tick **Select all**, then untick **FUEL** and **UNKNOWN**.
   - Also add `Sales` to Filters on this visual > **is greater than or equal to** `10000` > Apply. (This hides tiny
     departments such as TOYS, which has $4 of sales.)
   - Sort by Private Label Share, descending. Title: "Where does own label sell? Private label share".
   - Check: MISCELLANEOUS about 64.8%, SEAFOOD-PCKGD about 62.2%, PASTRY about 51.0% at the top.
4. **Optional drillthrough page:** add a new page `Department detail`. In the Visualizations pane, drag
   `Dim_Product[department]` into **Drill through** ("Add drill-through fields here"). Add a Line chart (X-axis
   `WeekLabel`, Y-axis `Sales`) and a Clustered bar chart (Y-axis `product_category`, X-axis `Sales`, Top N 10 by Sales).
   Power BI adds a back button. To use it: on the Departments page, right-click a department > **Drill through** >
   Department detail.
5. Alt text on each. Ctrl + S.

### Page 4: Discounts and coupons

New page, rename `Discounts`.

1. **Page filter first:** Filters pane > **Filters on this page** > drag `Dim_Product[IsFuel]` in > tick **False**.
   (Petrol has no discounts; leaving it in would dilute every percentage.)
2. **Discount by department:** **Clustered column chart**. X-axis `department`, Y-axis `Discount %`.
   - Filters on this visual: `Sales` **is greater than or equal to** `10000` (hides tiny departments).
   - Sort by Discount %, descending. Title: "Where do discounts go? Discount % of shelf value".
   - Check: SEAFOOD-PCKGD about 25.1%, MEAT about 25.0%, MEAT-PCKGD about 23.0% at the top.
3. **Discount over time:** **Line chart**. X-axis `WeekLabel`, Y-axis `Discount %`. Sort axis WeekLabel ascending.
   Title: "Is discounting rising or falling through the year?"
4. **Who funds the discount:** **Stacked bar chart**. Y-axis `department`; X-axis `Retail Discount` and
   `Coupon Match Discount` (both in X-axis; they stack). Add the same `Sales` ≥ 10000 visual filter. Title: "Retailer
   discount versus coupon match, by department". Retail discount will dwarf coupon match; that's correct.
5. **Manufacturer coupons:** **Card** with `Manufacturer Coupon Value`. Title: "Manufacturer coupons (funded by
   manufacturers, not in Discount %)". Check: $26,360.
6. Alt text on each. Ctrl + S.

### Page 5: Data quality and reconciliation

New page, rename `Data quality`.

1. **Six cards** in two rows:
   - Row 1: `Row Difference` (must show 0) and `Sales Difference` (must show $0.00).
   - Row 2: `Loaded Rows (all)` next to `Control Rows` (both 1,469,307); `Sales (all)` next to `Control Sales` (both
     $4,596,039.58).
   - Optional: on the two difference cards, Format visual > Visual > Callout value > colour > **fx** > Rules: if value is
     not equal to 0, red.
2. **Rule table:** **Table** visual. Columns: `DQ_Rules[RuleID]`, `DQ_Rules[Check]`, `DQ_Rules[Treatment]`,
   `DQ_Rules[ExpectedCount]`, and the measure `Actual (DQ rule)`.
   - In the Columns well, click the arrow next to `RuleID` > tick **Show items with no data** (otherwise DQ05 and DQ06,
     which are checked in SQL only and have no Actual, disappear).
   - Format visual > Visual > **Values** > Text wrap **on**; widen the Check and Treatment columns.
   - Check: Actual equals Expected for DQ01 (8,869), DQ02 (2,406), DQ03 (14,697), DQ04 (4,836), DQ07 (1), DQ08 (0).
     DQ05 and DQ06 show Expected 0 and a blank Actual, by design. DQ08 may take a few seconds: it checks every line.
3. **Assumptions text box:**
   - "Gross Sales = sales_value + retail_disc + coupon_match_disc, assuming sales_value is net of those discounts."
   - "US grocery data from 2017 (84.51°), in dollars; households are a sample of frequent shoppers."
   - "17 products are missing from the product file. Their 4,836 lines are only $173 of sales but carry $6,530 of
     manufacturer coupons (a quarter of the total), so they look like coupon-redemption lines."
4. No slicers on this page. Alt text on each. Ctrl + S.

### Make the slicers work across pages 1 to 4

1. On page 1, Ctrl + click the three slicers > Ctrl + C.
2. Go to page 2 > Ctrl + V. A box asks whether to sync the visuals: click **Sync**. Do the same on page 3.
3. On page 4, paste only the Month and Department slicers (page 4 already filters petrol out).
4. Check: pick a month on page 1, go to page 2; the same month is selected.

### Tab order (keyboard users)

On each page: **View** > **Selection** > **Tab order** tab > arrange top-left to bottom-right (heading, slicers, cards,
charts).

## Part 9. Final checks (10 minutes)

1. Clear every slicer (hover a slicer > eraser icon) so the report opens unfiltered.
2. DAX query view > your tests tab > **Run** again. Still 44 PASS and True, True, True.
3. Page 5: both differences still 0.
4. Click a store in the page 2 bar chart: the other visuals on that page filter to it. Click again to clear.
5. Ctrl + S.

## Part 10. Save, export, take home, clean up (20 minutes): before you leave the laptop

1. **Power BI project:** File > **Save as** > Save as type **Power BI project files (\*.pbip)** > folder
   `C:\storetrade\project\powerbi\pbip\` (create it) > name `storetrade` > Save. If that type isn't in the list:
   File > Options and settings > Options > **Preview features** > tick **Power BI Project (.pbip) save option** > OK,
   restart Power BI, open `storetrade.pbix`, and try again.
2. **PDF:** File > **Export** > **Export to PDF**. If it asks where to save, choose `C:\storetrade\project\docs\`; if it
   opens the PDF directly, save it from the viewer as `C:\storetrade\project\docs\storetrade_report.pdf`.
3. **Screenshots:** for each page, Windows key + Shift + S > drag around the canvas. Windows 11 saves them in
   Pictures\Screenshots; move them to `C:\storetrade\project\docs\img\` as `page1_overview.png`, `page2_stores.png`,
   `page3_departments.png`, `page4_discounts.png`, `page5_quality.png` (tests_pass.png is already there).
4. **Zip:** in File Explorer right-click `C:\storetrade\project` > **Compress to ZIP file** (Windows 11) or
   **Send to > Compressed (zipped) folder** (Windows 10).
5. **Get it home:** upload the zip to Google Drive or OneDrive in the browser, or copy it to a USB stick. If you email
   it to yourself and it's over 25 MB, Gmail will turn it into a Drive link; that's fine. Keep the `.pbix` for yourself,
   but don't put it on GitHub: it contains the data.
6. **Clean up your friend's laptop:**
   - Delete `C:\storetrade` and empty the Recycle Bin.
   - Delete the two downloaded zips from Downloads.
   - **Sign out of Claude, your email and Google Drive** in the browser.
   - Ask your friend whether to keep Power BI Desktop; if not: Settings > Apps > Power BI Desktop > Uninstall.

## Part 11. If something goes wrong

| Message or symptom | Cause and fix |
|---|---|
| Formula.Firewall: … references other queries or steps … rebuild this data combination | Privacy not set (part 1 step 2), or you pasted an old Dim_Product. Its first step must read `Products = Products_Raw` |
| DataSource.NotFound / could not find a part of the path | `Param_DataFolder` is wrong. It must be the folder holding the three CSVs and end with `\` |
| Expression.Error: The name '…' wasn't recognized | A query is misspelled or missing. Compare the names with the table in part 3 |
| We cannot convert a value of type DateTime to type Date | A date parameter was made as Date/Time. Home > Manage Parameters > change its Type to **Date** |
| DataFormat.Error when loading numbers | You used the first data zip. Replace the CSVs with storetrade_data_v2 and click Refresh |
| Load window reports errors | Screenshot and send it |
| Can't create a relationship / cardinality not valid | Make sure the "from" side is Fact_Sales (many) and the "to" side the Dim table (one) |
| Mark as date table refuses | You chose a column other than Dim_Date[Date], or Dim_Date didn't load 365 rows |
| DAX query view: table '_Measures' can't be found | Do part 6 steps 1 and 2 first, name exactly `_Measures` |
| A test says FAIL | Don't edit anything. Screenshot and send it |
| A visual says "Can't display the visual" | A field is in the wrong well. Compare with the steps; screenshot if it persists |
| Everything is slow | Normal on first load (1.47 million rows). Close other apps and give it a minute |

## Part 12. What to send me afterwards

1. `tests_pass.png` (or just tell me "44 of 44 PASS, True True True").
2. The PDF, or the page screenshots.
3. Any error screenshots.

Then I'll mark the repository as built in Power BI Desktop with 44 of 44 tests passing, add the screenshots to the
README, and update your CV.
