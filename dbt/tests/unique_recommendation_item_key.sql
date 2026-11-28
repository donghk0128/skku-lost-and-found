select run_id, candidate_post_id
from {{ ref('stg_recommendation_items') }}
group by 1, 2 having count(*) > 1
