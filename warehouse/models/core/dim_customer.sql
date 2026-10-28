select
    company_id,
    source_id,
    payload->>'code' as customer_code,
    payload->>'name' as customer_name,
    payload->>'active' as active,
    payload->>'deleted_at' as deleted_at
from {{ source('raw', 'records') }}
where table_name = 'customer'
