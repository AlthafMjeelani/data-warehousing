-- Any result fails the build. Do not publish dashboards after a failed build.
select company_id, source_id as identifier, 'invalid_header' as issue
from {{ ref('stg_sales_headers') }}
where sales_date is null or currency_code is null or nullif(invoice_no, '') is null
union all
select l.company_id, l.source_id, 'orphan_or_invalid_line'
from {{ ref('stg_sales_lines') }} l
left join {{ ref('stg_sales_headers') }} h
    on l.company_id = h.company_id and l.invoice_no = h.invoice_no
where h.source_id is null or l.sales_type not in ('sales', 'gr', 'expiry', 'damage', 'foc')
    or l.sales_type is null or l.taxable_amount is null or l.source_net_amount is null
    or l.tax_amount is null or l.pack_quantity is null or l.multiplier is null
    or l.multiplier <= 0 or nullif(l.detail_code, '') is null
