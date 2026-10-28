{% set checks = [
    ('stg_sales_headers', 'invoice_no'), ('stg_sales_lines', 'detail_code'),
    ('dim_customer', 'customer_code'), ('dim_product', 'product_code'),
    ('dim_route', 'route_code'), ('dim_employee', 'employee_code')
] %}
{% for model, key in checks %}
select company_id, '{{ model }}' as model, {{ key }} as identifier
from {{ ref(model) }}
where nullif({{ key }}, '') is not null
group by company_id, {{ key }} having count(*) > 1
{% if not loop.last %}union all{% endif %}
{% endfor %}
