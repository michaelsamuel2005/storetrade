// Query: Recon_Control   (Enable load: on). Control totals written by scripts/export_raw.R from the source object,
// before any Power BI step. The Reconciliation page compares them with what the model loaded.
let
    Source = Csv.Document(
        File.Contents(Param_DataFolder & "control_totals.csv"),
        [Delimiter = ",", Columns = 13, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {{"source", type text}, {"expected_rows", Int64.Type}, {"expected_sales_value", Currency.Type},
         {"expected_retail_disc", Currency.Type}, {"expected_coupon_disc", Currency.Type},
         {"expected_coupon_match_disc", Currency.Type}, {"expected_baskets", Int64.Type},
         {"expected_households", Int64.Type}, {"expected_stores", Int64.Type}, {"expected_products_sold", Int64.Type},
         {"expected_product_rows", Int64.Type}, {"min_date", type date}, {"max_date", type date}},
        "en-US"
    )
in
    Typed
