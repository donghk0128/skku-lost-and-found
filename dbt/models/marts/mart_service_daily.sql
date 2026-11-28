select date(occurred_at, 'Asia/Seoul') as activity_date,
       countif(event_type = 'screen_view') as screen_views,
       countif(event_type = 'post_view') as post_views,
       countif(event_type = 'post_created') as posts_created,
       countif(event_type = 'search_applied') as searches,
       countif(event_type = 'filter_applied') as filters,
       countif(event_type = 'chat_started') as chats_started,
       countif(event_type = 'return_completed') as returns_reported,
       countif(event_type = 'match_confirmed') as pair_confirmations,
       count(distinct user_id) as active_users_with_events
from {{ ref('stg_event_logs') }}
group by 1
