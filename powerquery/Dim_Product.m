// Query: Dim_Product   (Enable load: on). 92,331 products from the product file + 17 products that appear on sales lines but not in the file.
// References only other queries (Products_Raw, Transactions_Raw) and reads no file itself, so the Formula.Firewall allows it.
// DQ03: IsFuel marks petrol (product_type starts with GASOLINE). Its "quantity" is not a unit count, so Units measures exclude it.
// DQ04: sales-line products missing from the product file are added with department UNKNOWN, so no sales fall out of a chart.
let
    Products = Products_Raw,
    // keys that are on sales lines but not in the product file
    FactKeys = Table.Distinct(Table.SelectColumns(Transactions_Raw, {"product_id"})),
    Unmatched = Table.RemoveColumns(
        Table.NestedJoin(FactKeys, {"product_id"}, Products, {"product_id"}, "m", JoinKind.LeftAnti), {"m"}
    ),
    UnknownRows = Table.AddColumn(
        Table.AddColumn(
            Table.AddColumn(
                Table.AddColumn(
                    Table.AddColumn(
                        Table.AddColumn(Unmatched, "manufacturer_id", each null, type text),
                        "department", each "UNKNOWN", type text),
                    "brand", each "Unknown", type text),
                "product_category", each "UNKNOWN", type text),
            "product_type", each "UNKNOWN", type text),
        "package_size", each null, type text
    ),
    Combined = Table.Combine({Products, Table.ReorderColumns(UnknownRows, Table.ColumnNames(Products))}),
    AddFuel = Table.AddColumn(
        Combined, "IsFuel",
        each [product_type] <> null and Text.StartsWith([product_type], "GASOLINE"),
        type logical
    )
in
    AddFuel
