# Export The Complete Journey (84.51 degrees, completejourney R package) to CSV for Power BI.
# Usage: Rscript scripts/export_raw.R data
# Writes transactions.csv, products.csv and control_totals.csv (row count and sums taken from the source object,
# before any Power BI step, so the report can reconcile its load back to them).
args <- commandArgs(trailingOnly = TRUE)
out <- if (length(args)) args[1] else "data"
dir.create(out, showWarnings = FALSE, recursive = TRUE)

if (requireNamespace("completejourney", quietly = TRUE)) {
  tx <- completejourney::get_transactions()
  pr <- completejourney::products
  src <- paste("completejourney", as.character(utils::packageVersion("completejourney")))
} else {
  base <- "https://raw.githubusercontent.com/bradleyboehmke/completejourney/master/data/"
  tmp <- tempdir()
  utils::download.file(paste0(base, "transactions.rds"), file.path(tmp, "transactions.rds"), mode = "wb", quiet = TRUE)
  utils::download.file(paste0(base, "products.rda"), file.path(tmp, "products.rda"), mode = "wb", quiet = TRUE)
  tx <- readRDS(file.path(tmp, "transactions.rds"))
  e <- new.env(); load(file.path(tmp, "products.rda"), envir = e); pr <- e$products
  src <- "completejourney GitHub data files"
}

# Money to whole cents: 28 cells carry floating-point residue (largest 1.8e-15) that R would write in scientific
# notation (e.g. 1.776357e-15); every real value is already a whole number of cents, so rounding loses nothing.
options(scipen = 999)
for (v in c("sales_value", "retail_disc", "coupon_disc", "coupon_match_disc")) tx[[v]] <- round(tx[[v]], 2)
tx$quantity <- as.integer(round(tx$quantity))
# keep the local store time as stored (the object carries its own time zone); do not convert to UTC
tx$transaction_timestamp <- format(tx$transaction_timestamp, "%Y-%m-%d %H:%M:%S")
pr$brand <- as.character(pr$brand)
utils::write.csv(tx, file.path(out, "transactions.csv"), row.names = FALSE, na = "")
utils::write.csv(pr, file.path(out, "products.csv"), row.names = FALSE, na = "")

ts <- as.POSIXct(tx$transaction_timestamp, tz = "UTC")
ctl <- data.frame(
  source = src,
  expected_rows = nrow(tx),
  expected_sales_value = round(sum(tx$sales_value), 2),
  expected_retail_disc = round(sum(tx$retail_disc), 2),
  expected_coupon_disc = round(sum(tx$coupon_disc), 2),
  expected_coupon_match_disc = round(sum(tx$coupon_match_disc), 2),
  expected_baskets = length(unique(tx$basket_id)),
  expected_households = length(unique(tx$household_id)),
  expected_stores = length(unique(tx$store_id)),
  expected_products_sold = length(unique(tx$product_id)),
  expected_product_rows = nrow(pr),
  min_date = format(as.Date(min(ts))), max_date = format(as.Date(max(ts)))
)
utils::write.csv(ctl, file.path(out, "control_totals.csv"), row.names = FALSE)
print(t(ctl))
