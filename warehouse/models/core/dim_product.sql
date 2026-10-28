with records as (select * from {{ source('raw', 'records') }})
select
    p.company_id,
    p.source_id,
    p.payload->>'code' as product_code,
    p.payload->>'name' as product_name,
    c.payload->>'name' as category_name,
    s.payload->>'name' as subcategory_name,
    p.payload->>'deleted_at' as deleted_at
from records p
left join records c on c.company_id = p.company_id and c.table_name = 'p_category'
    and c.source_id = p.payload->>'category'
left join records s on s.company_id = p.company_id and s.table_name = 'p_subcategory'
    and s.source_id = p.payload->>'subcategory'
where p.table_name = 'product'
