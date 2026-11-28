select id, source_post_id, algorithm_version, candidate_count, generated_at
from {{ source('raw', 'recommendation_runs') }}
