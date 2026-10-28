select company_id, name as company_name, source_database, last_success_at,
    coverage_start, coverage_end
from {{ source('raw', 'companies') }}
