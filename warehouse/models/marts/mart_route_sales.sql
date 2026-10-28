select company_id, company_name, sales_date, currency_code,
    route_code, route_name, branch_name, area_name, region_name,
    sum(net_sales_excluding_tax) as net_sales_excluding_tax
from {{ ref('mart_sales_detail') }}
group by company_id, company_name, sales_date, currency_code,
    route_code, route_name, branch_name, area_name, region_name
