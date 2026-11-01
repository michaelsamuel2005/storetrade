// Query: Dim_Date   (Enable load: on; mark as date table on [Date]). One row per calendar day, 365 rows.
// Weeks reproduce the source: Monday-start, and week 1 is Sunday 1 January alone (rule DQ08 shows zero disagreements).
// IsPartialWeek is true for week 1 only (its other six days belong to the previous year): week-on-week and rolling measures skip it.
let
    Days = Duration.Days(Param_EndDate - Param_StartDate) + 1,
    Dates = List.Dates(Param_StartDate, Days, #duration(1, 0, 0, 0)),
    AsTable = Table.TransformColumnTypes(Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}), {{"Date", type date}}),
    AddYear = Table.AddColumn(AsTable, "Year", each Date.Year([Date]), Int64.Type),
    AddMonthNo = Table.AddColumn(AddYear, "MonthNo", each Date.Month([Date]), Int64.Type),
    AddMonth = Table.AddColumn(AddMonthNo, "Month", each Date.ToText([Date], "MMM", "en-GB"), type text),
    AddWeekStartRaw = Table.AddColumn(AddMonth, "WeekMonday", each Date.StartOfWeek([Date], Day.Monday), type date),
    AddWeekNo = Table.AddColumn(AddWeekStartRaw, "WeekNo",
        each Number.IntegerDivide(Duration.Days([WeekMonday] - #date(2016, 12, 26)), 7) + 1, Int64.Type),
    AddWeekStart = Table.AddColumn(AddWeekNo, "WeekStart", each List.Max({[WeekMonday], Param_StartDate}), type date),
    AddWeekLabel = Table.AddColumn(AddWeekStart, "WeekLabel", each "W" & Text.PadStart(Text.From([WeekNo]), 2, "0"), type text),
    AddDayNo = Table.AddColumn(AddWeekLabel, "DayNo", each Date.DayOfWeek([Date], Day.Monday) + 1, Int64.Type),
    AddDayName = Table.AddColumn(AddDayNo, "DayName", each Date.ToText([Date], "ddd", "en-GB"), type text),
    AddWeekend = Table.AddColumn(AddDayName, "IsWeekend", each [DayNo] >= 6, type logical),
    AddPartial = Table.AddColumn(AddWeekend, "IsPartialWeek", each [WeekMonday] < Param_StartDate, type logical),
    AddClosed = Table.AddColumn(AddPartial, "IsClosed", each List.Contains(Ref_ClosedDates[Date], [Date]), type logical),
    Final = Table.RemoveColumns(AddClosed, {"WeekMonday"})
in
    Final
