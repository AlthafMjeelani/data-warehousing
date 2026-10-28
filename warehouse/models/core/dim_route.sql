with records as (select * from {{ source('raw', 'records') }})
select
    r.company_id,
    r.source_id,
    r.payload->>'code' as route_code,
    r.payload->>'name' as route_name,
    b.payload->>'name' as branch_name,
    a.payload->>'name' as area_name,
    g.payload->>'name' as region_name
from records r
left join records b on b.company_id = r.company_id and b.table_name = 'branches'
    and b.source_id = r.payload->>'branch'
left join records a on a.company_id = r.company_id and a.table_name = 'area'
    and a.source_id = b.payload->>'area'
left join records g on g.company_id = r.company_id and g.table_name = 'region'
    and g.source_id = a.payload->>'region'
where r.table_name = 'route'
