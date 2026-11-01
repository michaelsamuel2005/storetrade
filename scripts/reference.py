"""Independent reference calculation for storetrade.

Mirrors, in DuckDB SQL, every cleaning rule in powerquery/ and every measure in powerbi/measures.dax, then writes
  outputs/reference_values.json   the expected value of each check
  outputs/reference_values.md     the same, readable
  powerbi/tests.dax               a DAX query for Power BI Desktop's DAX query view: expected vs actual, PASS/FAIL
  powerquery/DQ_Rules.m           the data-quality rule table loaded into the report
If Power BI disagrees with these numbers, the Power Query steps or the DAX are wrong (or the reading of a field is).

Usage: python3 scripts/reference.py [data_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data"
START, END = "2017-01-01", "2017-12-31"


def build(con: duckdb.DuckDBPyConnection) -> None:
    """Fact_Sales, Dim_Product, Dim_Store, Dim_Date exactly as the Power Query steps build them."""
    con.execute(f"create view tx_raw as select * from read_csv('{DATA}/transactions.csv', header=true, "
                "types={'household_id':'VARCHAR','store_id':'VARCHAR','basket_id':'VARCHAR','product_id':'VARCHAR',"
                "'transaction_timestamp':'TIMESTAMP'})")
    con.execute(f"create view pr_raw as select * from read_csv('{DATA}/products.csv', header=true, all_varchar=true)")
    con.execute("""
        create table fact as select household_id, store_id, basket_id, product_id, quantity, sales_value, retail_disc,
          coupon_disc, coupon_match_disc, week as source_week, transaction_timestamp,
          cast(transaction_timestamp as date) as date,
          sales_value + retail_disc + coupon_match_disc as shelf_value,
          case when quantity = 0 then 'Zero quantity' when sales_value = 0 then 'Free item' else 'Sale' end as line_flag
        from tx_raw""")
    con.execute("""
        create table dim_product as
        select product_id, manufacturer_id, department, brand, product_category, product_type, package_size,
               coalesce(product_type like 'GASOLINE%', false) as is_fuel from pr_raw
        union all
        select product_id, null, 'UNKNOWN', 'Unknown', 'UNKNOWN', 'UNKNOWN', null, false
        from (select distinct product_id from tx_raw) k where product_id not in (select product_id from pr_raw)""")
    con.execute("create table dim_store as select distinct store_id, 'Store ' || store_id as store_label from tx_raw")
    con.execute(f"""
        create table dim_date as
        with d as (select cast(unnest(generate_series(date '{START}', date '{END}', interval 1 day)) as date) as date)
        select date,
          date_trunc('week', date) as week_start,
          cast(datediff('day', date '2016-12-26', date_trunc('week', date)) / 7 as integer) + 1 as week_no,
          date_trunc('week', date) < date '{START}' as is_partial_week,
          date = date '2017-12-25' as is_closed
        from d""")


def main() -> None:
    con = duckdb.connect()
    build(con)
    q = lambda s: con.execute(s).fetchall()  # noqa: E731
    one = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
    r2 = lambda v: round(float(v), 2)  # noqa: E731
    F = "fact f join dim_product p using(product_id) join dim_date d on d.date = f.date"

    v: dict[str, tuple[float, str]] = {}  # name -> (expected, kind)  kind: money|count|ratio

    def put(name, val, kind):
        v[name] = (val, kind)

    put("Loaded rows", one("select count(*) from fact"), "count")
    put("Sales", r2(one("select sum(sales_value) from fact")), "money")
    put("Gross Sales", r2(one("select sum(shelf_value) from fact")), "money")
    put("Retail Discount", r2(one("select sum(retail_disc) from fact")), "money")
    put("Coupon Match Discount", r2(one("select sum(coupon_match_disc) from fact")), "money")
    put("Total Discount", r2(one("select sum(retail_disc + coupon_match_disc) from fact")), "money")
    put("Discount %", round(one("select sum(retail_disc + coupon_match_disc) / sum(shelf_value) from fact"), 6), "ratio")
    put("Manufacturer Coupon Value", r2(one("select sum(coupon_disc) from fact")), "money")
    put("Baskets", one("select count(distinct basket_id) from fact"), "count")
    put("Households", one("select count(distinct household_id) from fact"), "count")
    put("Stores", one("select count(distinct store_id) from fact"), "count")
    put("Trading days", one("select count(distinct date) from fact"), "count")
    put("Units (ex fuel)", r2(one(f"select sum(f.quantity) from {F} where not p.is_fuel")), "money")
    put("Sales ex Fuel", r2(one(f"select sum(f.sales_value) from {F} where not p.is_fuel")), "money")
    put("Fuel Sales", r2(one(f"select sum(f.sales_value) from {F} where p.is_fuel")), "money")
    put("Fuel Lines", one(f"select count(*) from {F} where p.is_fuel"), "count")
    # money divided by a count stays money in Power BI (fixed decimal, 4 decimal places), so compare to 4 places
    put("Avg Basket Value", round(one("select sum(sales_value) / count(distinct basket_id) from fact"), 4), "money4")
    baskets_xf = one(f"select count(distinct f.basket_id) from {F} where not p.is_fuel")
    units_xf = v["Units (ex fuel)"][0]
    put("Items per Basket", round(units_xf / baskets_xf, 6), "ratio")
    put("Avg Selling Price", round(v["Sales ex Fuel"][0] / units_xf, 4), "money4")
    put("Private Label Share", round(one(f"select sum(f.sales_value) filter (where p.brand='Private') / sum(f.sales_value) from {F} where not p.is_fuel"), 6), "ratio")
    put("Discount % ex Fuel", round(one(f"select sum(f.retail_disc + f.coupon_match_disc) / sum(f.shelf_value) from {F} where not p.is_fuel"), 6), "ratio")
    dept_xf = lambda d, num: one(f"select case when sum(f.sales_value) filter (where not p.is_fuel) >= 10000 then {num} end from {F} where p.department = '{d}'")  # noqa: E731
    put("Discount % (depts over $10k) at SEAFOOD-PCKGD", round(dept_xf("SEAFOOD-PCKGD", "sum(f.retail_disc + f.coupon_match_disc) filter (where not p.is_fuel) / sum(f.shelf_value) filter (where not p.is_fuel)"), 6), "ratio")
    put("Private Label Share (depts over $10k) at MISCELLANEOUS", round(dept_xf("MISCELLANEOUS", "sum(f.sales_value) filter (where not p.is_fuel and p.brand = 'Private') / sum(f.sales_value) filter (where not p.is_fuel)"), 6), "ratio")
    assert dept_xf("TOYS", "1") is None  # the report helpers must hide tiny departments
    put("Sales GROCERY", r2(one(f"select sum(f.sales_value) from {F} where p.department='GROCERY'")), "money")
    put("Share of Total GROCERY", round(v["Sales GROCERY"][0] / v["Sales"][0], 6), "ratio")
    put("Sales Store 367", r2(one("select sum(sales_value) from fact where store_id='367'")), "money")
    wk = lambda n: r2(one(f"select sum(f.sales_value) from fact f join dim_date d on d.date=f.date where d.week_no={n}"))  # noqa: E731
    put("Sales week 10", wk(10), "money")
    put("Sales PW at week 11", wk(10), "money")
    put("Sales WoW % at week 11", round((wk(11) - wk(10)) / wk(10), 6), "ratio")
    put("Rolling 4 Week Sales at week 20", r2(sum(wk(n) for n in (17, 18, 19, 20))), "money")
    put("Zero-Quantity Lines", one("select count(*) from fact where line_flag='Zero quantity'"), "count")
    put("Free-Item Lines", one("select count(*) from fact where line_flag='Free item'"), "count")
    put("Unknown-Product Lines", one(f"select count(*) from {F} where p.department='UNKNOWN'"), "count")
    put("Unknown-Product Sales", r2(one(f"select sum(f.sales_value) from {F} where p.department='UNKNOWN'")), "money")
    put("Zero-Quantity Sales", r2(one("select sum(sales_value) from fact where line_flag='Zero quantity'")), "money")
    put("Source week mismatch lines", one("select count(*) from fact f join dim_date d on d.date=f.date where f.source_week <> d.week_no"), "count")
    put("Negative value lines", one("select count(*) from fact where sales_value<0 or retail_disc<0 or coupon_disc<0 or coupon_match_disc<0"), "count")
    put("Exact duplicate lines", one("select coalesce(sum(n-1),0) from (select count(*) n from tx_raw group by household_id, store_id, basket_id, product_id, quantity, sales_value, retail_disc, coupon_disc, coupon_match_disc, week, transaction_timestamp having count(*)>1)"), "count")
    put("Orphan product keys", one("select count(*) from fact where product_id not in (select product_id from dim_product)"), "count")
    put("Orphan store keys", one("select count(*) from fact where store_id not in (select store_id from dim_store)"), "count")
    put("Orphan date keys", one("select count(*) from fact where date not in (select date from dim_date)"), "count")
    put("Dim_Product rows", one("select count(*) from dim_product"), "count")
    put("Dim_Store rows", one("select count(*) from dim_store"), "count")
    put("Dim_Date rows", one("select count(*) from dim_date"), "count")
    put("Closed days with sales", one("select count(*) from fact f join dim_date d on d.date=f.date where d.is_closed"), "count")
    put("Days with no sales (calendar)", one("select count(*) from dim_date where date not in (select distinct date from fact)"), "count")

    # control totals recorded at export time (independent of this script's SQL)
    ctl = con.execute(f"select * from read_csv('{DATA}/control_totals.csv', header=true)").fetchdf().iloc[0]
    agree = {
        "rows": int(ctl.expected_rows) == v["Loaded rows"][0],
        "sales": abs(float(ctl.expected_sales_value) - v["Sales"][0]) < 0.005,
        "baskets": int(ctl.expected_baskets) == v["Baskets"][0],
        "households": int(ctl.expected_households) == v["Households"][0],
        "stores": int(ctl.expected_stores) == v["Stores"][0],
        "product rows": int(ctl.expected_product_rows) == v["Dim_Product rows"][0] - one("select count(*) from dim_product where department='UNKNOWN'"),
    }
    assert all(agree.values()), agree

    out = {k: {"expected": val, "kind": kind} for k, (val, kind) in v.items()}
    out["_control_agreement"] = {k: bool(b) for k, b in agree.items()}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs" / "reference_values.json").write_text(json.dumps(out, indent=2))

    # ---- extra tables for the docs
    top_dep = q(f"select p.department, round(sum(f.sales_value),2) s from {F} group by 1 order by s desc limit 10")
    top_store = q("select store_id, round(sum(sales_value),2) s from fact group by 1 order by s desc limit 5")
    flags = q("select line_flag, count(*), round(sum(sales_value),2) from fact group by 1 order by 2 desc")
    md = ["# storetrade: reference values (DuckDB, independent of Power BI)", "",
          "Generated by `scripts/reference.py`. Power BI must reproduce these; `powerbi/tests.dax` checks them in Desktop.", "",
          "| check | expected |", "|---|---|"]
    for k, (val, kind) in v.items():
        md.append(f"| {k} | {val:,.2f} |" if kind == "money" else f"| {k} | {val:,.4f} |" if kind == "money4" else (f"| {k} | {val:.6f} |" if kind == "ratio" else f"| {k} | {val:,} |"))
    md += ["", "## Top 10 departments by sales", "", "| department | sales |", "|---|---|"] + [f"| {d} | {s:,.2f} |" for d, s in top_dep]
    md += ["", "## Top 5 stores by sales", "", "| store_id | sales |", "|---|---|"] + [f"| {a} | {s:,.2f} |" for a, s in top_store]
    md += ["", "## Line flags", "", "| line_flag | lines | sales |", "|---|---|---|"] + [f"| {a} | {n:,} | {s:,.2f} |" for a, n, s in flags]
    md += ["", "## Agreement with control_totals.csv (written by the R export before any Power BI step)", ""] + [f"- {k}: {'yes' if b else 'NO'}" for k, b in agree.items()]
    (ROOT / "outputs" / "reference_values.md").write_text("\n".join(md) + "\n")

    # ---- DAX test query: [Measure or expression, expected, name]
    dax_for = {
        "Loaded rows": "COUNTROWS ( Fact_Sales )",
        "Sales": "[Sales]", "Gross Sales": "[Gross Sales]", "Retail Discount": "[Retail Discount]",
        "Coupon Match Discount": "[Coupon Match Discount]", "Total Discount": "[Total Discount]", "Discount %": "[Discount %]",
        "Manufacturer Coupon Value": "[Manufacturer Coupon Value]", "Baskets": "[Baskets]", "Households": "[Households]",
        "Stores": "DISTINCTCOUNT ( Fact_Sales[store_id] )", "Trading days": "DISTINCTCOUNT ( Fact_Sales[Date] )",
        "Units (ex fuel)": "[Units]", "Sales ex Fuel": "[Sales ex Fuel]", "Fuel Sales": "[Fuel Sales]",
        "Fuel Lines": "[Fuel Lines]", "Avg Basket Value": "[Avg Basket Value]", "Items per Basket": "[Items per Basket]",
        "Avg Selling Price": "[Avg Selling Price]", "Private Label Share": "[Private Label Share]",
        "Sales GROCERY": 'CALCULATE ( [Sales], Dim_Product[department] = "GROCERY" )',
        "Share of Total GROCERY": 'CALCULATE ( [Share of Total Sales], Dim_Product[department] = "GROCERY" )',
        "Sales Store 367": 'CALCULATE ( [Sales], Dim_Store[store_id] = "367" )',
        "Sales week 10": "CALCULATE ( [Sales], Dim_Date[WeekNo] = 10 )",
        "Sales PW at week 11": "CALCULATE ( [Sales PW], Dim_Date[WeekNo] = 11 )",
        "Sales WoW % at week 11": "CALCULATE ( [Sales WoW %], Dim_Date[WeekNo] = 11 )",
        "Rolling 4 Week Sales at week 20": "CALCULATE ( [Rolling 4 Week Sales], Dim_Date[WeekNo] = 20 )",
        "Zero-Quantity Lines": "[Zero-Quantity Lines]", "Free-Item Lines": "[Free-Item Lines]",
        "Unknown-Product Lines": "[Unknown-Product Lines]", "Unknown-Product Sales": "[Unknown-Product Sales]",
        "Zero-Quantity Sales": "[Zero-Quantity Sales]",
        "Source week mismatch lines": "[Source Week Mismatch Lines]",
        "Dim_Product rows": "COUNTROWS ( Dim_Product )", "Dim_Store rows": "COUNTROWS ( Dim_Store )",
        "Dim_Date rows": "COUNTROWS ( Dim_Date )",
        "Closed days with sales": "CALCULATE ( COUNTROWS ( Fact_Sales ), Dim_Date[IsClosed] = TRUE () ) + 0",
        "Negative value lines": "[Negative-Value Lines]",
        "Exact duplicate lines": "[Exact Duplicate Lines]",
        "Discount % ex Fuel": "[Discount % ex Fuel]",
        "Discount % (depts over $10k) at SEAFOOD-PCKGD": 'CALCULATE ( [Discount % (depts over $10k)], Dim_Product[department] = "SEAFOOD-PCKGD" )',
        "Private Label Share (depts over $10k) at MISCELLANEOUS": 'CALCULATE ( [Private Label Share (depts over $10k)], Dim_Product[department] = "MISCELLANEOUS" )',
    }
    rows = []
    for k, expr in dax_for.items():
        exp, kind = v[k]
        tol = {"money": "0.01", "money4": "0.0001", "count": "0.5", "ratio": "0.000001"}[kind]  # plain decimals: DAX has no 1e-06 literal
        rows.append(f'    ROW ( "Check", "{k}", "Expected", {float(exp)!r}, "Actual", CONVERT ( {expr}, DOUBLE ), "Tolerance", {tol} )')
    # checks against the control file loaded by Power Query
    for nm, ex in [("Rows vs control_totals.csv", "[Loaded Rows (all)] - [Control Rows]"),
                   ("Sales vs control_totals.csv", "ROUND ( [Sales (all)] - [Control Sales], 2 )")]:
        rows.append(f'    ROW ( "Check", "{nm} (difference)", "Expected", 0.0, "Actual", CONVERT ( {ex}, DOUBLE ), "Tolerance", 0.005 )')
    dax = ["// storetrade: DAX tests. Paste into Power BI Desktop > DAX query view and Run.",
           "// Expected values come from scripts/reference.py (DuckDB, independent of Power BI). Generated: do not edit by hand.",
           "// Rolling-window and week-on-week blanks are tested separately at the bottom.",
           "EVALUATE", "VAR Results =", "  UNION (", ",\n".join(rows), "  )",
           "RETURN", "  SELECTCOLUMNS (",
           "    Results,", '    "Check", [Check],', '    "Expected", [Expected],', '    "Actual", [Actual],',
           '    "Result", IF ( ABS ( [Actual] - [Expected] ) <= [Tolerance], "PASS", "FAIL" )', "  )",
           "ORDER BY [Result], [Check]", "",
           "// Blank-by-design checks: week 2 has no full prior week (week 1 is one day); week 4 has only three full weeks; TOYS ($4 of sales) is hidden by the report helpers. All three must be TRUE",
           "EVALUATE",
           "ROW (",
           '  "WoW blank in week 2", ISBLANK ( CALCULATE ( [Sales WoW %], Dim_Date[WeekNo] = 2 ) ),',
           '  "Rolling 4 weeks blank in week 4", ISBLANK ( CALCULATE ( [Rolling 4 Week Sales], Dim_Date[WeekNo] = 4 ) ),',
           '  "Tiny department hidden (TOYS)", ISBLANK ( CALCULATE ( [Discount % (depts over $10k)], Dim_Product[department] = "TOYS" ) )',
           ")", ""]
    (ROOT / "powerbi" / "tests.dax").write_text("\n".join(dax))

    # ---- DQ rule table for the report
    rules = [
        ("DQ01", "Lines with quantity = 0", "Kept: the value counts in Sales, the line adds no units; flagged 'Zero quantity'", v["Zero-Quantity Lines"][0], v["Zero-Quantity Sales"][0]),
        ("DQ02", "Free items: quantity > 0 and sales_value = 0", "Kept: genuine promotional give-aways; flagged 'Free item'", v["Free-Item Lines"][0], 0.0),
        ("DQ03", "Petrol lines: 'quantity' is not a unit count (up to 89,638 on one line)", "Kept in Sales and Fuel Sales; excluded from Units, Items per Basket and Avg Selling Price", v["Fuel Lines"][0], v["Fuel Sales"][0]),
        ("DQ04", "Product on a sales line is missing from the product file", "Kept; mapped to department UNKNOWN so no sales fall out of a department chart", v["Unknown-Product Lines"][0], v["Unknown-Product Sales"][0]),
        ("DQ05", "Negative values (returns, voids)", "None found; the model does not handle returns", v["Negative value lines"][0], 0.0),
        ("DQ06", "Exact duplicate lines", "None found; no de-duplication step", v["Exact duplicate lines"][0], 0.0),
        ("DQ07", "Calendar days with no transactions", "25 December only; flagged IsClosed; per-day measures divide by trading days", v["Days with no sales (calendar)"][0], 0.0),
        ("DQ08", "Source week differs from the date table's week", "None; the date table reproduces the source's Monday-start weeks (week 1 = 1 January only)", v["Source week mismatch lines"][0], 0.0),
    ]
    esc = lambda s: s.replace('"', '""')  # noqa: E731
    body = ",\n".join(f'        {{"{a}", "{esc(b)}", "{esc(c)}", {int(n)}, {s!r}}}' for a, b, c, n, s in rules)
    m = ("// Query: DQ_Rules  (generated by scripts/reference.py: documentation table shown on the Data Quality page)\n"
         "let\n    Source = #table(\n        type table [RuleID = text, Check = text, Treatment = text, ExpectedCount = Int64.Type, ExpectedSales = Currency.Type],\n"
         "        {\n" + body + "\n        }\n    )\nin\n    Source\n")
    (ROOT / "powerquery" / "DQ_Rules.m").write_text(m)
    print(f"{len(v)} checks written; control totals agree: {all(agree.values())}")


if __name__ == "__main__":
    main()
