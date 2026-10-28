select company_id, sales_line_id
from {{ ref('mart_sales_detail') }}
group by company_id, sales_line_id having count(*) <> 1
