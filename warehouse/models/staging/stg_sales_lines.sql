select
    company_id,
    source_id,
    payload->>'detail_code' as detail_code,
    payload->>'sales_code' as invoice_no,
    payload->>'product_code' as product_code,
    payload->>'product_name' as product_name,
    lower(payload->>'sales_type') as sales_type,
    (payload->>'multipack_quantity')::numeric as pack_quantity,
    (payload->>'multiplier')::numeric as multiplier,
    payload->>'base_multipack_code' as base_uom,
    (payload->>'total_taxable_amount')::numeric as taxable_amount,
    (payload->>'tax_amount')::numeric as tax_amount,
    (payload->>'net_amount')::numeric as source_net_amount,
    (payload->>'discount_amount')::numeric as discount_amount,
    (payload->>'cost_price')::numeric as unit_cost
from {{ source('raw', 'records') }}
where table_name = 'sales_details'
