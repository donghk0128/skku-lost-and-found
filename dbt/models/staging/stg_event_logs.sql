select id, user_id, event_type, occurred_at, received_at, visit_id,
       post_id, source_post_id, candidate_post_id, run_id, rank,
       safe.parse_json(properties) as properties
from {{ source('raw', 'event_logs') }}
