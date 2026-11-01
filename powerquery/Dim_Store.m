// Query: Dim_Store   (Enable load: on). 457 stores. The extract has no store attributes (no region, format or size), only the id,
// so store comparisons are by store, not by region. In the model: sort store_label by store_no.
let
    Source = Table.Distinct(Table.SelectColumns(Transactions_Raw, {"store_id"})),
    AddNo = Table.AddColumn(Source, "store_no", each Number.From([store_id]), Int64.Type),
    AddLabel = Table.AddColumn(AddNo, "store_label", each "Store " & [store_id], type text),
    Sorted = Table.Sort(AddLabel, {{"store_no", Order.Ascending}})
in
    Sorted
