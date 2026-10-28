select
    f.*,
    c.company_name,
    coalesce(p.product_name, f.transaction_product_name) as product_name,
    p.category_name,
    coalesce(u.customer_name, f.transaction_customer_name) as customer_name,
    coalesce(r.route_name, f.transaction_route_name) as route_name,
    r.branch_name,
    r.area_name,
    r.region_name,
    coalesce(e.employee_name, f.transaction_employee_name) as employee_name
from {{ ref('fact_sales_line') }} f
join {{ ref('dim_company') }} c using (company_id)
left join {{ ref('dim_product') }} p
    on p.company_id = f.company_id and p.product_code = f.product_code
left join {{ ref('dim_customer') }} u
    on u.company_id = f.company_id and u.customer_code = f.customer_code
left join {{ ref('dim_route') }} r
    on r.company_id = f.company_id and r.route_code = f.route_code
left join {{ ref('dim_employee') }} e
    on e.company_id = f.company_id and e.employee_code = f.employee_code
