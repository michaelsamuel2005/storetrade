// Query: Products_Raw   (Enable load: off)
// Staging query: reads products.csv and sets types, nothing else. Kept separate from Dim_Product so that no query both
// reads a file and references another query (that combination triggers Power Query's Formula.Firewall error).
let
    Source = Csv.Document(
        File.Contents(Param_DataFolder & "products.csv"),
        [Delimiter = ",", Columns = 7, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]
    ),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Typed = Table.TransformColumnTypes(
        Promoted,
        {{"product_id", type text}, {"manufacturer_id", type text}, {"department", type text}, {"brand", type text},
         {"product_category", type text}, {"product_type", type text}, {"package_size", type text}},
        "en-US"
    )
in
    Typed
