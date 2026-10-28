with bounds as (
    select min(sales_date) as first_date, max(sales_date) as last_date
    from {{ ref('stg_sales_headers') }}
)
select
    d::date as date_day,
    to_char(d, 'YYYYMMDD')::integer as date_key,
    extract(year from d)::integer as year,
    extract(quarter from d)::integer as quarter,
    extract(month from d)::integer as month,
    date_trunc('month', d)::date as month_start,
    extract(isodow from d)::integer as weekday
from bounds, generate_series(first_date::timestamp, last_date::timestamp, interval '1 day') d
