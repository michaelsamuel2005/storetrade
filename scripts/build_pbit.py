"""Build storetrade.pbit: a Power BI template holding the whole semantic model and the five report pages.

Sources of truth: powerquery/*.m (queries), powerbi/measures.dax (measures). Nothing is retyped here.
Opening the template in Power BI Desktop asks for the data folder, loads the CSVs and gives the finished report.

Steps:
  1. Build the model as TMSL (build/model.bim).
  2. If Microsoft's Tabular Object Model is available (TOM_DIR with tomcheck.exe and the TOM DLLs, run under mono),
     validate it, write the canonical TMSL (used as DataModelSchema) and a TMDL copy (powerbi/semantic_model/).
  3. Build the report layout (legacy Power BI layout JSON, the format of Microsoft's own sample reports).
  4. Check that every field a visual uses exists in the model.
  5. Package dist/storetrade.pbit.

Usage: [TOM_DIR=/path/to/tom] python3 scripts/build_pbit.py
       powerbi/template_base/ holds Version, Settings, Metadata and the base theme from a file saved by the target
       Power BI Desktop (2.149, November 2025), so the template matches that version.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PQ = ROOT / "powerquery"
BUILD = ROOT / "build"
DIST = ROOT / "dist"
BASE = ROOT / "powerbi" / "template_base"  # Version, Settings, Metadata, content types and theme from the user's own Desktop

# ------------------------------------------------------------------ measures: parse powerbi/measures.dax
CUR0 = r"\$#,0;-\$#,0;\$#,0"
CUR2 = r"\$#,0.00;-\$#,0.00;\$#,0.00"
PCT1 = "0.0%;-0.0%;0.0%"
DEC1 = "#,0.0"
INT = "#,0"
FORMATS = {
    CUR0: ["Sales", "Gross Sales", "Retail Discount", "Coupon Match Discount", "Total Discount", "Manufacturer Coupon Value",
           "Sales ex Fuel", "Fuel Sales", "Sales per Trading Day", "Sales PW", "Rolling 4 Week Sales",
           "Retail Discount (depts over $10k)", "Coupon Match Discount (depts over $10k)"],
    CUR2: ["Avg Basket Value", "Avg Selling Price", "Zero-Quantity Sales", "Unknown-Product Sales", "Sales (all)", "Control Sales",
           "Sales Difference"],
    PCT1: ["Discount %", "Discount % ex Fuel", "Private Label Share", "Share of Total Sales", "Share of Department Sales",
           "Sales WoW %", "Sales vs Store Avg %", "Discount % (depts over $10k)", "Private Label Share (depts over $10k)"],
    DEC1: ["Items per Basket"],
    INT: ["Baskets", "Households", "Units", "Store Rank", "Zero-Quantity Lines", "Free-Item Lines", "Fuel Lines",
          "Unknown-Product Lines", "Source Week Mismatch Lines", "Negative-Value Lines", "Exact Duplicate Lines",
          "Loaded Rows (all)", "Control Rows", "Row Difference", "Actual (DQ rule)"],
}
FOLDERS = {
    "1 Sales and discounts": ["Sales", "Gross Sales", "Retail Discount", "Coupon Match Discount", "Total Discount", "Discount %",
                              "Discount % ex Fuel", "Manufacturer Coupon Value"],
    "2 Baskets and units": ["Baskets", "Households", "Units", "Sales ex Fuel", "Fuel Sales", "Avg Basket Value", "Items per Basket",
                            "Avg Selling Price", "Private Label Share"],
    "3 Mix and ranking": ["Share of Total Sales", "Share of Department Sales", "Store Rank", "Sales vs Store Avg %"],
    "4 Time": ["Sales per Trading Day", "Sales PW", "Sales WoW %", "Rolling 4 Week Sales"],
    "5 Data quality": ["Zero-Quantity Lines", "Zero-Quantity Sales", "Free-Item Lines", "Fuel Lines", "Unknown-Product Lines",
                       "Unknown-Product Sales", "Source Week Mismatch Lines", "Negative-Value Lines", "Exact Duplicate Lines"],
    "6 Reconciliation": ["Loaded Rows (all)", "Sales (all)", "Control Rows", "Control Sales", "Row Difference", "Sales Difference",
                         "Actual (DQ rule)"],
    "7 Report helpers": ["Discount % (depts over $10k)", "Private Label Share (depts over $10k)",
                         "Retail Discount (depts over $10k)", "Coupon Match Discount (depts over $10k)"],
}


def parse_measures(path: Path) -> list[dict]:
    lines = path.read_text().splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip() == "DEFINE")
    end = next(i for i, l in enumerate(lines) if l.strip().startswith("EVALUATE"))
    out, cur, pending = [], None, []
    for raw in lines[start + 1:end]:
        s = raw.strip()
        m = re.match(r"MEASURE _Measures\[(.+?)\] =(.*)$", s)
        if m:
            if cur:
                # trailing comments belong to the next measure (its description), not to this expression
                while cur["lines"] and (not cur["lines"][-1].strip() or cur["lines"][-1].strip().startswith("//")):
                    c = cur["lines"].pop().strip()
                    if c.startswith("//") and not c.startswith("// ----------"):
                        pending.insert(0, c[2:].strip())
                out.append(cur)
            cur = {"name": m.group(1), "lines": [m.group(2).strip()] if m.group(2).strip() else [], "desc": " ".join(pending)}
            pending = []
        elif cur is not None:
            cur["lines"].append(raw)
    if cur:
        while cur["lines"] and (not cur["lines"][-1].strip() or cur["lines"][-1].strip().startswith("//")):
            cur["lines"].pop()
        out.append(cur)
    for mm in out:
        body = mm.pop("lines")
        cont = [l for l in body[1:] if l.strip()] if body and body[0] else [l for l in body if l.strip()]
        indent = min((len(l) - len(l.lstrip()) for l in cont), default=0)
        text = [body[0]] if body and body[0] else []
        text += [l[indent:] for l in (body[1:] if body and body[0] else body)]
        mm["expression"] = "\n".join(t for t in text).strip()
    return out


# ------------------------------------------------------------------ model (TMSL)
def m_text(name: str) -> str:
    return (PQ / f"{name}.m").read_text().strip()


def param_expr(name: str) -> str:
    return "\n".join(l for l in m_text(name).splitlines() if not l.strip().startswith("//")).strip()


def tag() -> str:
    return str(uuid.uuid4())


def col(name, dtype, hidden=False, fmt=None, sort_by=None, key=False, date=False, summarize=None):
    c = {"name": name, "dataType": dtype, "sourceColumn": name, "lineageTag": tag()}
    if fmt:
        c["formatString"] = fmt
    if hidden:
        c["isHidden"] = True
    if key:
        c["isKey"] = True
    if sort_by:
        c["sortByColumn"] = sort_by
    numeric = dtype in ("int64", "double", "decimal")
    c["summarizeBy"] = summarize or ("none" if numeric else "none")
    ann = [{"name": "SummarizationSetBy", "value": "User" if numeric else "Automatic"}]
    if date:
        ann.append({"name": "UnderlyingDateTimeDataType", "value": "Date"})
    c["annotations"] = ann
    return c


def table(name, columns, measures=None, data_category=None):
    t = {"name": name, "lineageTag": tag(), "columns": columns,
         "partitions": [{"name": name, "mode": "import", "source": {"type": "m", "expression": m_text(name).splitlines()}}],
         "annotations": [{"name": "PBI_NavigationStepName", "value": "Navigation"}, {"name": "PBI_ResultType", "value": "Table"}]}
    if measures:
        t["measures"] = measures
    if data_category:
        t["dataCategory"] = data_category
    return t


def build_model(measures: list[dict]) -> dict:
    fmt_of = {n: f for f, names in FORMATS.items() for n in names}
    folder_of = {n: f for f, names in FOLDERS.items() for n in names}
    missing = [m["name"] for m in measures if m["name"] not in fmt_of or m["name"] not in folder_of]
    assert not missing, f"measures without a format or folder: {missing}"
    tm = []
    for m in measures:
        d = {"name": m["name"], "expression": m["expression"].splitlines(), "formatString": fmt_of[m["name"]],
             "displayFolder": folder_of[m["name"]], "lineageTag": tag()}
        if m["desc"]:
            d["description"] = m["desc"]
        if fmt_of[m["name"]] in (CUR0, CUR2):
            d["annotations"] = [{"name": "PBI_FormatHint", "value": "{\"currencyCulture\":\"en-US\"}"}]
        tm.append(d)

    fact = table("Fact_Sales", [
        col("Date", "dateTime", hidden=True, fmt="Short Date", date=True),
        col("transaction_timestamp", "dateTime", hidden=True, fmt="General Date"),
        col("basket_id", "string", hidden=True), col("household_id", "string", hidden=True),
        col("store_id", "string", hidden=True), col("product_id", "string", hidden=True),
        col("quantity", "double", hidden=True, fmt="#,0"),
        col("sales_value", "decimal", hidden=True, fmt=CUR2), col("retail_disc", "decimal", hidden=True, fmt=CUR2),
        col("coupon_match_disc", "decimal", hidden=True, fmt=CUR2), col("coupon_disc", "decimal", hidden=True, fmt=CUR2),
        col("shelf_value", "decimal", hidden=True, fmt=CUR2),
        col("line_flag", "string"),
        col("source_week", "int64", hidden=True, fmt="0"),
    ])
    product = table("Dim_Product", [
        col("product_id", "string"), col("manufacturer_id", "string"), col("department", "string"), col("brand", "string"),
        col("product_category", "string"), col("product_type", "string"), col("package_size", "string"),
        col("IsFuel", "boolean", fmt='"TRUE";"TRUE";"FALSE"'),
    ])
    store = table("Dim_Store", [
        col("store_id", "string", hidden=True), col("store_no", "int64", hidden=True, fmt="0"),
        col("store_label", "string", sort_by="store_no"),
    ])
    date = table("Dim_Date", [
        col("Date", "dateTime", fmt="Short Date", key=True, date=True),
        col("Year", "int64", fmt="0"), col("MonthNo", "int64", hidden=True, fmt="0"), col("Month", "string", sort_by="MonthNo"),
        col("WeekNo", "int64", hidden=True, fmt="0"), col("WeekStart", "dateTime", fmt="Short Date", date=True),
        col("WeekLabel", "string", sort_by="WeekNo"), col("DayNo", "int64", hidden=True, fmt="0"),
        col("DayName", "string", sort_by="DayNo"),
        col("IsWeekend", "boolean", fmt='"TRUE";"TRUE";"FALSE"'), col("IsPartialWeek", "boolean", fmt='"TRUE";"TRUE";"FALSE"'),
        col("IsClosed", "boolean", fmt='"TRUE";"TRUE";"FALSE"'),
    ], data_category="Time")
    recon = table("Recon_Control", [
        col("source", "string"), col("expected_rows", "int64", fmt="#,0"), col("expected_sales_value", "decimal", fmt=CUR2),
        col("expected_retail_disc", "decimal", fmt=CUR2), col("expected_coupon_disc", "decimal", fmt=CUR2),
        col("expected_coupon_match_disc", "decimal", fmt=CUR2), col("expected_baskets", "int64", fmt="#,0"),
        col("expected_households", "int64", fmt="#,0"), col("expected_stores", "int64", fmt="#,0"),
        col("expected_products_sold", "int64", fmt="#,0"), col("expected_product_rows", "int64", fmt="#,0"),
        col("min_date", "dateTime", fmt="Short Date", date=True), col("max_date", "dateTime", fmt="Short Date", date=True),
    ])
    rules = table("DQ_Rules", [
        col("RuleID", "string"), col("Check", "string"), col("Treatment", "string"),
        col("ExpectedCount", "int64", fmt="#,0"), col("ExpectedSales", "decimal", fmt=CUR2),
    ])
    meas_tbl = {"name": "_Measures", "lineageTag": tag(),
                "columns": [col("Column1", "string", hidden=True)],
                "partitions": [{"name": "_Measures", "mode": "import",
                                "source": {"type": "m", "expression": [
                                    "// Holds the measures only (Home > Enter data equivalent)",
                                    "#table(type table [Column1 = text], {})"]}}],
                "measures": tm,
                "annotations": [{"name": "PBI_ResultType", "value": "Table"}]}

    def shared(name, result):
        return {"name": name, "kind": "m", "lineageTag": tag(),
                "expression": (param_expr(name) if result != "Table" else m_text(name)).splitlines(),
                "annotations": [{"name": "PBI_NavigationStepName", "value": "Navigation"},
                                {"name": "PBI_ResultType", "value": result}]}

    expressions = [shared("Param_DataFolder", "Text"), shared("Param_StartDate", "Date"), shared("Param_EndDate", "Date"),
                   shared("Ref_ClosedDates", "Table"), shared("Transactions_Raw", "Table"), shared("Products_Raw", "Table")]
    order = ["Param_DataFolder", "Param_StartDate", "Param_EndDate", "Ref_ClosedDates", "Transactions_Raw", "Products_Raw",
             "Fact_Sales", "Dim_Product", "Dim_Store", "Dim_Date", "Recon_Control", "DQ_Rules", "_Measures"]
    rel = lambda f, t, c, tc=None: {"name": tag(), "fromTable": f, "fromColumn": c, "toTable": t, "toColumn": tc or c}  # noqa: E731
    return {
        "name": tag(),
        "compatibilityLevel": 1550,
        "model": {
            "culture": "en-GB",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-GB",
            "tables": [fact, product, store, date, recon, rules, meas_tbl],
            "relationships": [rel("Fact_Sales", "Dim_Product", "product_id"), rel("Fact_Sales", "Dim_Store", "store_id"),
                              rel("Fact_Sales", "Dim_Date", "Date")],
            "expressions": expressions,
            "annotations": [{"name": "PBI_QueryOrder", "value": json.dumps(order)},
                            {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                            {"name": "PBIDesktopVersion", "value": "2.149.178.0 (25.11)"}],
        },
    }


# ------------------------------------------------------------------ report (legacy layout JSON)
def lit(s: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + s.replace("'", "''") + "'"}}}


def literal(v: str) -> dict:
    return {"expr": {"Literal": {"Value": v}}}


class Page:
    def __init__(self, name: str):
        self.name, self.visuals, self.z = name, [], 1000

    def _container(self, sv: dict, x, y, w, h, filters=None):
        cfg = {"name": secrets.token_hex(10),
               "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": self.z, "width": w, "height": h, "tabOrder": self.z}}],
               "singleVisual": sv}
        self.visuals.append({"x": x, "y": y, "z": self.z, "width": w, "height": h, "config": json.dumps(cfg),
                             "filters": json.dumps(filters or []), "tabOrder": self.z})
        self.z += 1000

    def text(self, paragraphs: list[tuple[str, str, bool]], x, y, w, h):
        paras = [{"textRuns": [{"value": t, "textStyle": {"fontSize": size, **({"fontWeight": "bold"} if bold else {})}}]}
                 for t, size, bold in paragraphs]
        self._container({"visualType": "textbox", "drillFilterOtherVisuals": True,
                         "objects": {"general": [{"properties": {"paragraphs": paras}}]}}, x, y, w, h)

    def visual(self, vtype, roles, x, y, w, h, title=None, alt=None, order=None, objects=None, filters=None, sync=None):
        """roles: {role: [("c"|"m", entity, property), ...]}; order: [("c"|"m", entity, property, 1 asc | 2 desc)]."""
        aliases, frm = {}, []

        def src(entity):
            if entity not in aliases:
                a = re.sub(r"[^a-z]", "", entity.lower())[:1] or "t"
                a = a + str(len(aliases)) if a in aliases.values() else a
                aliases[entity] = a
                frm.append({"Name": a, "Entity": entity, "Type": 0})
            return aliases[entity]

        def expr(kind, entity, prop):
            node = "Column" if kind == "c" else "Measure"
            return {node: {"Expression": {"SourceRef": {"Source": src(entity)}}, "Property": prop}}

        select, proj, seen = [], {}, set()
        for role, fields in roles.items():
            proj[role] = []
            for i, (kind, entity, prop) in enumerate(fields):
                ref = f"{entity}.{prop}"
                if ref not in seen:
                    seen.add(ref)
                    select.append({**expr(kind, entity, prop), "Name": ref, "NativeReferenceName": prop})
                p = {"queryRef": ref}
                if kind == "c" and role in ("Category", "Rows", "Values", "Group") and vtype != "tableEx" or (vtype == "slicer"):
                    p["active"] = True
                proj[role].append(p)
        pq = {"Version": 2, "From": frm, "Select": select}
        if order:
            pq["OrderBy"] = [{"Direction": d, "Expression": expr(k, e, p)} for k, e, p, d in order]
        sv = {"visualType": vtype, "projections": proj, "prototypeQuery": pq, "drillFilterOtherVisuals": True}
        if order:
            sv["hasDefaultSort"] = True
        if objects:
            sv["objects"] = objects
        vco = {}
        if title:
            vco["title"] = [{"properties": {"show": literal("true"), "text": lit(title)}}]
        if alt:
            vco["general"] = [{"properties": {"altText": lit(alt)}}]
        if vco:
            sv["vcObjects"] = vco
        if sync:
            sv["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
        self._container(sv, x, y, w, h, filters)

    def json(self, ordinal: int) -> dict:
        return {"name": "ReportSection" + secrets.token_hex(10), "displayName": self.name, "filters": "[]", "ordinal": ordinal,
                "visualContainers": self.visuals, "config": "{}", "displayOption": 1, "width": 1280, "height": 720}


def topn_filter(entity, prop, n, measure):
    col_expr = lambda s: {"Column": {"Expression": {"SourceRef": {"Source": s}}, "Property": prop}}  # noqa: E731
    return {"name": "Filter" + secrets.token_hex(8),
            "expression": {"Column": {"Expression": {"SourceRef": {"Entity": entity}}, "Property": prop}},
            "filter": {"Version": 2,
                       "From": [{"Name": "subquery", "Expression": {"Subquery": {"Query": {
                           "Version": 2,
                           "From": [{"Name": "d", "Entity": entity, "Type": 0}, {"Name": "m", "Entity": "_Measures", "Type": 0}],
                           "Select": [{**col_expr("d"), "Name": "field"}],
                           "OrderBy": [{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": "m"}},
                                                                                     "Property": measure}}}],
                           "Top": n}}}, "Type": 2},
                                {"Name": "d", "Entity": entity, "Type": 0}],
                       "Where": [{"Condition": {"In": {"Expressions": [col_expr("d")], "Table": {"SourceRef": {"Source": "subquery"}}}}}]},
            "type": "TopN", "howCreated": 1}


M = "_Measures"


def mm(*names):
    return [("m", M, n) for n in names]


def build_layout(base_layout: dict) -> dict:
    pages = []
    slicer_obj = {"data": [{"properties": {"mode": lit("Dropdown")}}]}

    def heading(p, title, sub):
        p.text([(title, "18pt", True), (sub, "10pt", False)], 20, 8, 820, 56)

    def page_slicers(p, x0):
        p.visual("slicer", {"Values": [("c", "Dim_Date", "Month")]}, x0, 10, 200, 52, objects=slicer_obj, sync="Month",
                 alt="Month slicer")
        p.visual("slicer", {"Values": [("c", "Dim_Product", "department")]}, x0 + 210, 10, 200, 52, objects=slicer_obj,
                 sync="Department", alt="Department slicer")

    # Page 1: trading overview
    p = Page("Trading overview")
    heading(p, "storetrade: store and category trading, 2017",
            "US grocery data (84.51°, The Complete Journey), in US dollars. Week 1 is one day; 25 December has no transactions.")
    page_slicers(p, 640)
    p.visual("slicer", {"Values": [("c", "Dim_Product", "IsFuel")]}, 1060, 10, 200, 52, objects=slicer_obj, sync="IsFuel",
             alt="Petrol lines slicer: TRUE shows petrol only")
    cards = [("Sales", "Sales after discounts"), ("Discount %", "Discount as a share of shelf value"), ("Baskets", "Shopping trips"),
             ("Avg Basket Value", "Sales per basket"), ("Items per Basket", "Units per basket, petrol excluded"),
             ("Private Label Share", "Own-label share of non-fuel sales")]
    for i, (mname, alt) in enumerate(cards):
        p.visual("card", {"Values": mm(mname)}, 20 + i * 208, 76, 198, 96, alt=f"{mname}: {alt}")
    p.visual("lineClusteredColumnComboChart",
             {"Category": [("c", "Dim_Date", "WeekLabel")], "Y": mm("Sales"), "Y2": mm("Rolling 4 Week Sales"),
              "Tooltips": mm("Sales WoW %", "Sales per Trading Day")},
             20, 184, 830, 452, title="How are weekly sales trending? Bars: week; line: last four full weeks",
             alt="Weekly sales as columns with the rolling four-week total as a line, weeks 1 to 53",
             order=[("c", "Dim_Date", "WeekLabel", 1)],
             objects={"categoryAxis": [{"properties": {"axisType": lit("Categorical")}}],
                      "legend": [{"properties": {"show": literal("true"), "position": lit("Top")}}]})
    p.visual("clusteredColumnChart", {"Category": [("c", "Dim_Date", "DayName")], "Y": mm("Sales per Trading Day")},
             866, 184, 394, 452, title="Which days trade best? Sales per trading day",
             alt="Average sales per trading day for each weekday, Monday to Sunday",
             order=[("c", "Dim_Date", "DayName", 1)])
    p.text([("Petrol counts in Sales but not in units or items per basket (its 'quantity' is not a unit count). "
             "Week 53 has six trading days because Christmas Day is closed.", "9pt", False)], 20, 646, 1240, 50)
    pages.append(p)

    # Page 2: stores
    p = Page("Stores")
    heading(p, "Stores: which stores lead and lag?",
            "The extract has no store attributes (region, size, format), so stores are compared with each other.")
    page_slicers(p, 850)
    p.visual("tableEx", {"Values": [("c", "Dim_Store", "store_label")] + mm("Store Rank", "Sales", "Sales vs Store Avg %", "Baskets",
                                                                           "Avg Basket Value", "Discount %")},
             20, 76, 720, 624, title="Top 25 stores by sales", alt="Table of the 25 stores with the highest sales, ranked",
             order=[("m", M, "Store Rank", 1)], filters=[topn_filter("Dim_Store", "store_label", 25, "Sales")])
    p.visual("clusteredBarChart", {"Category": [("c", "Dim_Store", "store_label")], "Y": mm("Sales")},
             756, 76, 504, 300, title="Top 15 stores by sales", alt="Bar chart of the 15 stores with the highest sales",
             order=[("m", M, "Sales", 2)], filters=[topn_filter("Dim_Store", "store_label", 15, "Sales")])
    p.visual("scatterChart", {"Category": [("c", "Dim_Store", "store_label")], "X": mm("Baskets"), "Y": mm("Avg Basket Value"),
                              "Size": mm("Sales")},
             756, 388, 504, 312, title="Do stores win on visits or on basket size?",
             alt="Scatter of stores: number of baskets against average basket value, bubble size is sales")
    pages.append(p)

    # Page 3: departments
    p = Page("Departments")
    heading(p, "Departments and categories: what sells, and at what price?",
            "Expand a department to see its categories. Petrol has no average selling price because its quantity is not units.")
    page_slicers(p, 850)
    p.visual("pivotTable", {"Rows": [("c", "Dim_Product", "department"), ("c", "Dim_Product", "product_category")],
                            "Values": mm("Sales", "Share of Total Sales", "Share of Department Sales", "Discount %",
                                         "Avg Selling Price")},
             20, 76, 760, 624, title="Sales, share, discount and price by department and category",
             alt="Matrix of departments, expandable to categories, with sales, shares, discount and average selling price",
             order=[("m", M, "Sales", 2)])
    p.visual("treemap", {"Group": [("c", "Dim_Product", "department")], "Values": mm("Sales")},
             796, 76, 464, 300, title="Share of sales by department", alt="Treemap of sales by department")
    p.visual("clusteredBarChart", {"Category": [("c", "Dim_Product", "department")], "Y": mm("Private Label Share (depts over $10k)")},
             796, 388, 464, 312, title="Where does own label sell? Private label share",
             alt="Private label share of non-fuel sales by department, departments under 10,000 dollars hidden",
             order=[("m", M, "Private Label Share (depts over $10k)", 2)])
    pages.append(p)

    # Page 4: discounts
    p = Page("Discounts")
    heading(p, "Discounts and coupons: where do discounts go?",
            "Petrol excluded; departments under $10,000 of non-fuel sales hidden so tiny ones (TOYS: $4) do not distort the view.")
    page_slicers(p, 850)
    p.visual("clusteredColumnChart", {"Category": [("c", "Dim_Product", "department")], "Y": mm("Discount % (depts over $10k)")},
             20, 76, 620, 312, title="Discount % of shelf value by department",
             alt="Discount as a share of shelf value by department, highest first",
             order=[("m", M, "Discount % (depts over $10k)", 2)])
    p.visual("lineChart", {"Category": [("c", "Dim_Date", "WeekLabel")], "Y": mm("Discount % ex Fuel")},
             656, 76, 604, 312, title="Is discounting rising or falling through the year?",
             alt="Weekly discount percentage excluding petrol, weeks 1 to 53", order=[("c", "Dim_Date", "WeekLabel", 1)],
             objects={"categoryAxis": [{"properties": {"axisType": lit("Categorical")}}]})
    p.visual("barChart", {"Category": [("c", "Dim_Product", "department")],
                          "Y": mm("Retail Discount (depts over $10k)", "Coupon Match Discount (depts over $10k)")},
             20, 400, 900, 300, title="Retailer discount versus coupon match, by department",
             alt="Stacked bars of retailer loyalty discount and coupon match discount by department",
             order=[("m", M, "Retail Discount (depts over $10k)", 2)],
             objects={"legend": [{"properties": {"show": literal("true"), "position": lit("Top")}}]})
    p.visual("card", {"Values": mm("Manufacturer Coupon Value")}, 936, 400, 324, 140,
             title="Manufacturer coupons (funded by manufacturers, not in Discount %)",
             alt="Total value of manufacturer-funded coupons")
    p.text([("17 products missing from the product file account for a quarter of manufacturer coupon value on only $173 of "
             "sales: they look like coupon-redemption lines.", "9pt", False)], 936, 552, 324, 148)
    pages.append(p)

    # Page 5: data quality
    p = Page("Data quality")
    heading(p, "Data quality and reconciliation: can the numbers be trusted?",
            "Loaded rows and sales are compared with control totals written by the export before Power BI saw the data.")
    for i, (mname, alt) in enumerate([("Row Difference", "Loaded rows minus control rows; must be 0"),
                                      ("Sales Difference", "Loaded sales minus control sales; must be 0")]):
        p.visual("card", {"Values": mm(mname)}, 20 + i * 316, 76, 300, 96, alt=alt)
    for i, (mname, alt) in enumerate([("Loaded Rows (all)", "Rows loaded into the model"), ("Control Rows", "Rows in the export"),
                                      ("Sales (all)", "Sales loaded into the model"), ("Control Sales", "Sales in the export")]):
        p.visual("card", {"Values": mm(mname)}, 20 + i * 316, 184, 300, 96, alt=alt)
    p.visual("tableEx", {"Values": [("c", "DQ_Rules", "RuleID"), ("c", "DQ_Rules", "Check"), ("c", "DQ_Rules", "Treatment"),
                                    ("c", "DQ_Rules", "ExpectedCount")] + mm("Actual (DQ rule)")},
             20, 292, 1240, 300, title="Data-quality rules: expected count against what the model finds",
             alt="Table of eight data-quality rules with the expected and actual counts", order=[("c", "DQ_Rules", "RuleID", 1)])
    p.text([("Assumptions", "11pt", True),
            ("Gross Sales = sales_value + retail_disc + coupon_match_disc, assuming sales_value is net of those discounts.", "9pt", False),
            ("US grocery data from 2017 (84.51°), in dollars; households are a sample of frequent shoppers.", "9pt", False),
            ("Money was rounded to whole cents at export: 28 cells carried floating-point residue (largest 1.8e-15).", "9pt", False)],
           20, 602, 1240, 100)
    pages.append(p)

    lay = {k: v for k, v in base_layout.items() if k in ("id", "resourcePackages", "config", "layoutOptimization")}
    lay["sections"] = [pg.json(i) for i, pg in enumerate(pages)]
    cfg = json.loads(lay["config"])
    cfg["activeSectionIndex"] = 0
    lay["config"] = json.dumps(cfg)
    return lay


# ------------------------------------------------------------------ checks
def check_fields(layout: dict, model: dict) -> list[str]:
    known = {}
    for t in model["model"]["tables"]:
        known[t["name"]] = {"c": {c["name"] for c in t["columns"]}, "m": {m["name"] for m in t.get("measures", [])}}
    errors, used = [], 0

    def walk(node, aliases):
        nonlocal used
        if isinstance(node, dict):
            for kind, key in (("c", "Column"), ("m", "Measure")):
                if key in node and isinstance(node[key], dict) and "Property" in node[key]:
                    sr = node[key]["Expression"]["SourceRef"]
                    ent = sr.get("Entity") or aliases.get(sr.get("Source"))
                    if ent is not None:
                        used += 1
                        if ent not in known or node[key]["Property"] not in known[ent][kind]:
                            errors.append(f"{kind}:{ent}[{node[key]['Property']}]")
            for v in node.values():
                walk(v, aliases)
        elif isinstance(node, list):
            for v in node:
                walk(v, aliases)

    def aliases_of(q):
        return {f["Name"]: f.get("Entity") for f in q.get("From", []) if f.get("Entity")}

    for sec in layout["sections"]:
        for vc in sec["visualContainers"]:
            sv = json.loads(vc["config"]).get("singleVisual", {})
            pq = sv.get("prototypeQuery")
            if pq:
                walk(pq, aliases_of(pq))
                refs = {s["Name"] for s in pq["Select"]}
                for role, ps in sv.get("projections", {}).items():
                    errors += [f"projection {p['queryRef']} not selected" for p in ps if p["queryRef"] not in refs]
            for flt in json.loads(vc["filters"]):
                walk(flt["expression"], {})
                f = flt["filter"]
                for fr in f["From"]:
                    if "Expression" in fr:
                        q = fr["Expression"]["Subquery"]["Query"]
                        walk(q, aliases_of(q))
                walk(f["Where"], aliases_of(f))
    return errors, used


# ------------------------------------------------------------------ main
def utf16(s: str) -> bytes:
    return s.encode("utf-16-le")


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)
    measures = parse_measures(ROOT / "powerbi" / "measures.dax")
    model = build_model(measures)
    (BUILD / "model.bim").write_text(json.dumps(model, indent=2))
    print(f"model: {len(model['model']['tables'])} tables, {len(measures)} measures, {len(model['model']['expressions'])} shared queries")

    schema_text = json.dumps(model, indent=2)
    tom = os.environ.get("TOM_DIR")
    if tom and Path(tom, "tomcheck.exe").exists():
        out = subprocess.run(["mono", str(Path(tom, "tomcheck.exe")), str(BUILD / "model.bim"), str(BUILD / "model.canonical.bim"),
                              str(ROOT / "powerbi" / "semantic_model")],
                             cwd=tom, env={**os.environ, "MONO_PATH": tom}, capture_output=True, text=True)
        print(out.stdout.strip())
        if out.returncode != 0:
            print(out.stderr[-3000:])
            raise SystemExit("TOM rejected the model")
        schema_text = (BUILD / "model.canonical.bim").read_text()
        print("TOM: model validated; DataModelSchema is the canonical TOM serialisation; TMDL written to powerbi/semantic_model/")
    else:
        print("TOM not available: model not validated by Microsoft's library")

    ref = {str(p.relative_to(BASE)).replace("\\", "/"): p.read_bytes() for p in BASE.rglob("*") if p.is_file()}
    base_layout = json.loads(ref["Report/Layout"].decode("utf-16-le"))
    layout = build_layout(base_layout)
    errors, used = check_fields(layout, model)
    n_vis = sum(len(s["visualContainers"]) for s in layout["sections"])
    print(f"layout: {len(layout['sections'])} pages, {n_vis} visuals, {used} field references checked, {len(errors)} errors")
    assert not errors, errors
    (BUILD / "Layout.json").write_text(json.dumps(layout, indent=2))

    ct = ref["[Content_Types].xml"].decode("utf-8-sig")
    ct = ct.replace('<Override PartName="/DataModel" ContentType="" />', '<Override PartName="/DataModelSchema" ContentType="" />')
    ct = ct.replace('<Override PartName="/SecurityBindings" ContentType="" />', "")
    theme = [n for n in ref if n.startswith("Report/StaticResources/")]
    target = DIST / "storetrade.pbit"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Version", ref["Version"])
        z.writestr("[Content_Types].xml", ("﻿" + ct).encode("utf-8"))
        z.writestr("DataModelSchema", utf16(schema_text))
        z.writestr("Report/Layout", utf16(json.dumps(layout)))
        z.writestr("Settings", ref["Settings"])
        z.writestr("Metadata", ref["Metadata"])
        for n in theme:
            z.writestr(n, ref[n])
    print(f"written {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")

    # Fallback: the same model and report as a Power BI project folder (legacy formats: model.bim and report.json)
    proj = DIST / "storetrade_pbip"
    if proj.exists():
        shutil.rmtree(proj)
    (proj / "storetrade.SemanticModel").mkdir(parents=True)
    (proj / "storetrade.Report").mkdir(parents=True)
    (proj / "storetrade.pbip").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json", "version": "1.0", "artifacts": [{"report": {"path": "storetrade.Report"}}],
                                                       "settings": {"enableAutoRecovery": True}}, indent=2))
    (proj / "storetrade.SemanticModel" / "definition.pbism").write_text(json.dumps({"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json", "version": "1.0", "settings": {}}, indent=2))
    (proj / "storetrade.SemanticModel" / "model.bim").write_text(schema_text)
    (proj / "storetrade.Report" / "definition.pbir").write_text(json.dumps(
        {"$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/1.0.0/schema.json", "version": "1.0", "datasetReference": {"byPath": {"path": "../storetrade.SemanticModel"}, "byConnection": None}}, indent=2))
    (proj / "storetrade.Report" / "report.json").write_text(json.dumps(layout, indent=2))
    for n in theme:
        dst = proj / "storetrade.Report" / n.replace("Report/", "", 1)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(ref[n])
    (proj / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
    shutil.make_archive(str(DIST / "storetrade_pbip"), "zip", proj)
    print(f"written dist/storetrade_pbip.zip (fallback project folder)")


if __name__ == "__main__":
    main()
