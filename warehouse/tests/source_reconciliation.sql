-- Independent raw-to-mart check, by company and currency. No cross-currency summation.
with expected as (
    select h.company_id, h.currency_code,
        sum(case when l.sales_type = 'sales' then abs(l.taxable_amount)
            when l.sales_type in ('gr','expiry','damage') then -abs(l.taxable_amount)
            else 0 end) as amount
    from {{ ref('stg_sales_headers') }} h
    join {{ ref('stg_sales_lines') }} l
        on h.company_id = l.company_id and h.invoice_no = l.invoice_no
    where not h.is_void
    group by h.company_id, h.currency_code
), actual as (
    select company_id, currency_code, sum(net_sales_excluding_tax) as amount
    from {{ ref('mart_daily_sales') }} group by company_id, currency_code
)
select coalesce(e.company_id, a.company_id) as company_id
from expected e full join actual a using (company_id, currency_code)
where e.amount is distinct from a.amount
