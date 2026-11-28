select id, post_type, category_id, status, creation_method,
       event_start_at, event_end_at, created_at, updated_at, deleted_at
from {{ source('raw', 'posts') }}
