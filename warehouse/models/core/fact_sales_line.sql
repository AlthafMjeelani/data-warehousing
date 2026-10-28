select
    l.company_id,
    l.source_id as sales_line_id,
    l.detail_code,
    h.invoice_no,
    h.sales_date,
    h.customer_code,
    h.customer_name as transaction_customer_name,
    l.product_code,
    l.product_name as transaction_product_name,
    h.route_code,
    h.route_name as transaction_route_name,
    h.employee_code,
    h.employee_name as transaction_employee_name,
    h.currency_code,
    l.sales_type,
    l.base_uom,
    abs(l.pack_quantity * l.multiplier) as quantity_base_unit,
    abs(l.taxable_amount) as transaction_value_excluding_tax,
    abs(l.source_net_amount) as transaction_value_including_tax,
    abs(l.tax_amount) as transaction_tax_amount,
    abs(coalesce(l.discount_amount, 0)) as transaction_discount_amount,
    case when l.sales_type = 'sales' then abs(l.taxable_amount) else 0 end as sales_excluding_tax,
    case when l.sales_type in ('gr', 'expiry', 'damage')
        then abs(l.taxable_amount) else 0 end as returns_excluding_tax,
    case when l.sales_type = 'sales' then abs(l.taxable_amount)
        when l.sales_type in ('gr', 'expiry', 'damage') then -abs(l.taxable_amount)
        else 0 end as net_sales_excluding_tax,
    case when l.sales_type = 'sales' then abs(l.source_net_amount)
        when l.sales_type in ('gr', 'expiry', 'damage') then -abs(l.source_net_amount)
        else 0 end as signed_value_including_tax,
    l.unit_cost as source_unit_cost,
    h.loaded_at
from {{ ref('stg_sales_lines') }} l
join {{ ref('stg_sales_headers') }} h
    on h.company_id = l.company_id and h.invoice_no = l.invoice_no
where not h.is_void
