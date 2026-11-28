select run_id, rank
from {{ ref('stg_recommendation_items') }}
group by 1, 2 having count(*) > 1
