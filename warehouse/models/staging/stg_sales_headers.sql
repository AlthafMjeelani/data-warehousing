select
    company_id,
    source_id,
    payload->>'invoice_no' as invoice_no,
    (payload->>'sales_date')::date as sales_date,
    payload->>'customer_code' as customer_code,
    payload->>'customer_name' as customer_name,
    payload->>'route_code' as route_code,
    payload->>'route_name' as route_name,
    payload->>'salesman_code' as employee_code,
    payload->>'salesman_name' as employee_name,
    nullif(payload->>'currency_code', '') as currency_code,
    coalesce((payload->>'void')::integer, 0) <> 0 as is_void,
    (payload->>'net_amount')::numeric as source_invoice_total,
    loaded_at
from {{ source('raw', 'records') }}
where table_name = 'sales_summary'
