select company_id, company_name, sales_date, currency_code, customer_code, customer_name,
    sum(net_sales_excluding_tax) as net_sales_excluding_tax,
    count(distinct invoice_no) as invoice_count
from {{ ref('mart_sales_detail') }}
group by company_id, company_name, sales_date, currency_code, customer_code, customer_name
