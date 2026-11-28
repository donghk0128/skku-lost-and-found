select id
from {{ ref('stg_return_pairs') }}
where status = 'CONFIRMED' and confirmed_at is null
