select id, room_id, lost_post_id, found_post_id, status, created_at, confirmed_at
from {{ source('raw', 'return_pairs') }}
