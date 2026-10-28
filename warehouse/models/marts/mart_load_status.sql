select c.company_id, c.name as company_name, c.last_success_at,
    c.coverage_start, c.coverage_end,
    r.run_id, r.started_at, r.finished_at, r.status, r.mode, r.rows_loaded, r.error_type
from {{ source('raw', 'companies') }} c
left join lateral (
    select * from {{ source('raw', 'load_runs') }} r
    where r.company_id = c.company_id order by started_at desc limit 1
) r on true
