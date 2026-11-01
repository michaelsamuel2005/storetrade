// Query: Transactions_Raw   (Enable load: off)
// Step 1 of the data flow: read the CSV as exported, set types. No rows are removed or changed here.
// Keys are text on purpose (store_id "330" is a label, not a number; text keys also match the product file exactly).
let
    Source = Csv.Document(
        File.Contents(Param_DataFolder & "transactions.csv"),
        [Delimiter = ",", Columns = 11, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {
            {"household_id", type text}, {"store_id", type text}, {"basket_id", type text}, {"product_id", type text},
            {"quantity", type number},
            {"sales_value", Currency.Type}, {"retail_disc", Currency.Type},
            {"coupon_disc", Currency.Type}, {"coupon_match_disc", Currency.Type},
            {"week", Int64.Type}, {"transaction_timestamp", type datetime}
        },
        "en-US"
    )
in
    Typed
