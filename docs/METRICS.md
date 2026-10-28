# Sales metric contract

## Grain and identity

One fact row represents one source `sales_details.id` for a company, joined to its invoice through `sales_details.sales_code = sales_summary.invoice_no`.
Every join includes `company_id`.
Source IDs and business codes are not assumed to be globally unique.

## Default definitions

| Measure | Definition |
|---|---|
| Sales excluding tax | Absolute line `total_taxable_amount` for `sales` lines |
| Returns excluding tax | Absolute line `total_taxable_amount` for `gr`, `expiry`, and `damage` lines |
| Net sales excluding tax | Sales excluding tax minus returns excluding tax |
| FOC | Preserved as its own transaction type; zero contribution to net sales |
| Base quantity | Absolute `multipack_quantity * multiplier`; grouped with base UOM |
| Invoice count | Distinct invoice numbers within the displayed company/date/currency grain |
| Buying customers | Distinct customer codes within the displayed company/date/currency grain |

Void invoice headers are excluded.
Raw records remain available to audit their exclusion.
Other statuses are not filtered automatically; confirm whether your source uses non-void pending invoices before loading business data.
Unknown line types and missing financial fields fail data checks rather than silently being interpreted as ordinary sales.

The model assumes return amounts may be positive or negative and uses transaction type to determine their contribution.
Do not subtract returns again from an already netted header amount.
Discount amounts are exposed separately, but are not subtracted again from taxable amounts.
Invoice-level discounts and rounding allocations must be verified against the source application's calculations before interpreting the line-derived KPI as recognized revenue.

## Currency

Every monetary summary includes source currency.
No exchange-rate conversion or cross-currency total is implemented.
Even matching currency codes do not by themselves establish consolidated group revenue: intercompany sales and elimination rules are outside this first slice.

## History and aggregation

Dimensions represent current source masters, using full refreshes.
Transaction-time names are preserved on facts, while reporting names and route hierarchies use the current masters when available.
Historical slowly changing dimensions and historical manager assignments are not implemented.
Full loads mirror source changes and hard deletions; they are not an immutable audit archive.
Date-window full loads replace that company's transaction records with only the inclusive requested period.
Master records are still loaded fully; coverage dates are recorded in `raw.companies` and exposed in `marts.mart_load_status`.
An unrestricted incremental load is rejected while a company is date-windowed.

Do not sum daily distinct customer counts to obtain monthly unique customers.
For monthly counts, query distinct customers from `marts.mart_sales_detail` at the required grain.
Do not sum quantities across different products/UOMs unless the business considers that total meaningful.

`source_unit_cost` is preserved for investigation.
Gross margin is intentionally not published until the business confirms whether cost is per base unit or pack, whether returned stock reverses COGS, and whether the stored cost is historical.

## Validation

dbt checks required dates/currencies/line values, known sales types, orphan lines, duplicate business keys, join fanout and source-to-mart totals.
The reconciliation test confirms transformation consistency using the same documented line-based definition; it does not independently validate the business definition against the application's official report.
Before business use, reconcile a trusted reporting period independently by company and currency, including mixed invoices, returns, FOC, voids, discounts and rounding.

## Next business slices

Add collections and invoice allocations before daily receivable snapshots.
Then add targets at their actual period/scope, inventory movements and snapshots, delivery allocations and planned-versus-actual visits.
Each additional process needs its own fact grain, incremental loading strategy and independent source reconciliation.
