select company_id, source_id, payload->>'code' as employee_code,
    payload->>'name' as employee_name
from {{ source('raw', 'records') }}
where table_name = 'users'
