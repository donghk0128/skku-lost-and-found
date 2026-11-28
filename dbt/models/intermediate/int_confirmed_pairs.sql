-- Only a two-party confirmed pair can be used as a user-verified label.
select id, room_id, lost_post_id, found_post_id, confirmed_at
from {{ ref('stg_return_pairs') }}
where status = 'CONFIRMED' and confirmed_at is not null
