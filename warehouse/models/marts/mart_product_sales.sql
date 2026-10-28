select company_id, company_name, sales_date, currency_code,
    product_code, product_name, category_name, base_uom,
    sum(net_sales_excluding_tax) as net_sales_excluding_tax,
    sum(case when sales_type = 'sales' then quantity_base_unit else 0 end) as sold_quantity
from {{ ref('mart_sales_detail') }}
group by company_id, company_name, sales_date, currency_code,
    product_code, product_name, category_name, base_uom
