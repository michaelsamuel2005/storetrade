# Data flow

```mermaid
flowchart LR
    A[completejourney package<br/>84.51°, US grocer, 2017] -->|scripts/export_raw.R| B[transactions.csv<br/>products.csv]
    A -->|same script, from the source object| C[control_totals.csv]
    B --> D[Transactions_Raw<br/>types only, no rows changed]
    B --> P[Products_Raw<br/>types only]
    P --> E[Dim_Product<br/>+ unknown products, IsFuel]
    D --> E
    D --> F[Fact_Sales<br/>Date, shelf_value, line_flag]
    D --> G[Dim_Store]
    H[Param_StartDate/EndDate<br/>Ref_ClosedDates] --> I[Dim_Date]
    C --> J[Recon_Control]
    F & E & G & I --> K[Semantic model<br/>3 relationships, measures]
    J --> K
    L[DQ_Rules<br/>generated] --> K
    K --> M[Report: 5 pages]
    K -->|powerbi/tests.dax| N[Expected vs actual<br/>from scripts/reference.py]
```

| Step | What happens | Rows in → out | Where |
|---|---|---|---|
| Export | Source object written to CSV; control totals taken from the source | 1,469,307 → 1,469,307 | `scripts/export_raw.R` |
| Transactions_Raw | Read, text keys, money as fixed decimal, timestamp parsed. Nothing removed | 1,469,307 → 1,469,307 | `powerquery/Transactions_Raw.m` |
| Fact_Sales | Adds Date, shelf_value, line_flag; renames week to source_week | 1,469,307 → 1,469,307 | `powerquery/Fact_Sales.m` |
| Products_Raw | Read products.csv, set types (staging, not loaded) | 92,331 → 92,331 | `powerquery/Products_Raw.m` |
| Dim_Product | Products_Raw + products on sales lines but not in the file; IsFuel. Reads no file itself (avoids the Formula.Firewall) | 92,331 + 17 | `powerquery/Dim_Product.m` |
| Dim_Store | Distinct store ids | 457 | `powerquery/Dim_Store.m` |
| Dim_Date | One row per day; Monday-start weeks matching the source; partial and closed flags | 365 | `powerquery/Dim_Date.m` |
| Reconcile | Model rows and sales compared with `control_totals.csv` | difference must be 0 | Reconciliation page; `tests.dax` |

No line is deleted anywhere in the flow. Issues are flagged or handled in a dimension, so the report always reconciles to the
source (rows, sales value) and every treatment is a visible rule (`docs/BUSINESS_RULES.md`).
