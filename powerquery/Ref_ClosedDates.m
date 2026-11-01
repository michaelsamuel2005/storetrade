// Query: Ref_ClosedDates   (Enable load: off)
// Calendar days with no transactions in the extract, found by comparing every calendar day with the dates in the data (rule DQ07).
// Christmas Day: the stores were closed, so a zero is not a trading result. Add a row if a refresh brings new data.
let
    Source = #table(
        type table [Date = date, Reason = text],
        {
            {#date(2017, 12, 25), "Christmas Day: no transactions in the extract"}
        }
    )
in
    Source
