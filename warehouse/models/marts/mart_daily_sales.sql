select
    company_id, company_name, sales_date, currency_code,
    sum(sales_excluding_tax) as sales_excluding_tax,
    sum(returns_excluding_tax) as returns_excluding_tax,
    sum(net_sales_excluding_tax) as net_sales_excluding_tax,
    count(distinct invoice_no) as invoice_count,
    count(distinct customer_code) as buying_customers
from {{ ref('mart_sales_detail') }}
group by company_id, company_name, sales_date, currency_code
