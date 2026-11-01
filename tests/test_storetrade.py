"""storetrade checks that need no Power BI: reference identities, and consistency between the M, DAX, test and doc files."""
import datetime as dt
import json
import re
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REF = {k: v["expected"] for k, v in json.load(open(ROOT / "outputs" / "reference_values.json")).items() if not k.startswith("_")}
MEASURES = (ROOT / "powerbi" / "measures.dax").read_text()
TESTS = (ROOT / "powerbi" / "tests.dax").read_text()


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute(f"create view t as select * from read_csv('{DATA}/transactions.csv', header=true, types={{'transaction_timestamp':'TIMESTAMP','product_id':'VARCHAR','store_id':'VARCHAR'}})")
    c.execute(f"create view p as select * from read_csv('{DATA}/products.csv', header=true, all_varchar=true)")
    return c


def test_control_totals_match_source(con):
    ctl = con.execute(f"select * from read_csv('{DATA}/control_totals.csv', header=true)").fetchdf().iloc[0]
    rows, sales = con.execute("select count(*), round(sum(sales_value),2) from t").fetchone()
    assert ctl.expected_rows == rows == REF["Loaded rows"]
    assert abs(ctl.expected_sales_value - sales) < 0.005 and abs(sales - REF["Sales"]) < 0.005


def test_no_line_removed_and_flags_partition(con):
    n = con.execute("select count(*) from t").fetchone()[0]
    parts = con.execute("""select sum(quantity=0), sum(quantity<>0 and sales_value=0), sum(quantity<>0 and sales_value<>0) from t""").fetchone()
    assert sum(parts) == n
    assert parts[0] == REF["Zero-Quantity Lines"] and parts[1] == REF["Free-Item Lines"]


def test_money_identities(con):
    r = con.execute("select sum(sales_value), sum(retail_disc), sum(coupon_match_disc), sum(sales_value+retail_disc+coupon_match_disc) from t").fetchone()
    assert abs(r[3] - (r[0] + r[1] + r[2])) < 0.01
    assert abs(REF["Gross Sales"] - r[3]) < 0.01
    assert abs(REF["Total Discount"] - (REF["Retail Discount"] + REF["Coupon Match Discount"])) < 0.01
    assert abs(REF["Sales ex Fuel"] + REF["Fuel Sales"] - REF["Sales"]) < 0.01


def test_fuel_rule_is_needed(con):
    # the reason DQ03 exists: petrol quantities are not unit counts
    mx = con.execute("select max(quantity) from t join p using(product_id) where p.product_type like 'GASOLINE%'").fetchone()[0]
    other = con.execute("select max(quantity) from t join p using(product_id) where p.product_type not like 'GASOLINE%'").fetchone()[0]
    assert mx > 10_000 and other < 200


def test_unknown_products_are_exactly_those_missing_from_file(con):
    missing = con.execute("select count(distinct product_id) from t where product_id not in (select product_id from p)").fetchone()[0]
    assert REF["Dim_Product rows"] - 92331 == missing == 17


def test_week_formula_in_dim_date_m_matches_every_source_week(con):
    """Re-implements Dim_Date.m's WeekNo formula in Python and compares it with the source week of every line."""
    def week_no(d: dt.date) -> int:
        monday = d - dt.timedelta(days=d.weekday())             # Date.StartOfWeek(d, Day.Monday)
        return (monday - dt.date(2016, 12, 26)).days // 7 + 1   # Number.IntegerDivide(Duration.Days(...), 7) + 1
    rows = con.execute("select cast(transaction_timestamp as date) d, week, count(*) from t group by 1, 2").fetchall()
    assert all(week_no(d) == wk for d, wk, _ in rows)
    m = (ROOT / "powerquery" / "Dim_Date.m").read_text()
    assert "#date(2016, 12, 26)" in m and "Day.Monday" in m and "Number.IntegerDivide" in m


def test_closed_day_is_in_ref_table_and_has_no_sales(con):
    assert "#date(2017, 12, 25)" in (ROOT / "powerquery" / "Ref_ClosedDates.m").read_text()
    assert con.execute("select count(*) from t where cast(transaction_timestamp as date) = date '2017-12-25'").fetchone()[0] == 0


def test_every_dax_measure_used_is_defined():
    defined = set(re.findall(r"MEASURE _Measures\[([^\]]+)\]", MEASURES))
    used = set(re.findall(r"(?<![A-Za-z_])\[([A-Za-z][^\]]*)\]", MEASURES + TESTS)) - {"Check", "Expected", "Actual", "Tolerance", "Result"}
    # column references look the same as measure references only when unqualified; qualified ones are filtered by the lookbehind
    assert used <= defined, sorted(used - defined)


def test_dax_columns_exist_in_power_query():
    produced = {
        "Fact_Sales": "Date transaction_timestamp basket_id household_id store_id product_id quantity sales_value retail_disc coupon_match_disc coupon_disc shelf_value line_flag source_week",
        "Dim_Product": "product_id manufacturer_id department brand product_category product_type package_size IsFuel",
        "Dim_Store": "store_id store_no store_label",
        "Dim_Date": "Date Year MonthNo Month WeekNo WeekStart WeekLabel DayNo DayName IsWeekend IsPartialWeek IsClosed",
        "Recon_Control": "expected_rows expected_sales_value", "DQ_Rules": "RuleID Check Treatment ExpectedCount ExpectedSales"}
    for tbl, col in set(re.findall(r"(Fact_Sales|Dim_Product|Dim_Store|Dim_Date|Recon_Control|DQ_Rules)\[([^\]]+)\]", MEASURES + TESTS)):
        assert col in produced[tbl].split(), (tbl, col)
    # and the M files really name those columns
    for tbl, cols in produced.items():
        src = "".join(p.read_text() for p in (ROOT / "powerquery").glob("*.m"))
        for c in cols.split():
            assert c in src, (tbl, c)


def test_tests_dax_carries_every_reference_value():
    sql_only = {"Orphan product keys", "Orphan store keys", "Orphan date keys",
                "Days with no sales (calendar)"}  # the model cannot contain these (relationships and the date table rule them out)
    for k, v in REF.items():
        if k not in sql_only:
            assert repr(float(v)) in TESTS, k
    # one DAX check per reference value except the SQL-only ones, plus the two control-file differences
    assert TESTS.count('ROW ( "Check"') == len(REF) - len(sql_only) + 2


def test_m_files_balanced():
    for f in (ROOT / "powerquery").glob("*.m"):
        s = re.sub(r"//.*", "", f.read_text())
        s = re.sub(r'"(?:[^"]|"")*"', '""', s)
        for a, b in ("()", "[]", "{}"):
            assert s.count(a) == s.count(b), (f.name, a)


def test_docs_quote_reference_numbers():
    readme = (ROOT / "README.md").read_text()
    assert f"{REF['Sales']:,.2f}" in readme and f"{REF['Loaded rows']:,.0f}" in readme
    rules = (ROOT / "docs" / "BUSINESS_RULES.md").read_text()
    assert f"{REF['Fuel Sales']:,.2f}" in rules and f"{REF['Unknown-Product Lines']:,.0f}" in rules
