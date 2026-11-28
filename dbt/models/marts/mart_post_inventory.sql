select post_type,
       countif(deleted_at is null and status = 'OPEN') as open_posts,
       countif(deleted_at is null and status = 'COMPLETED') as completed_posts,
       countif(deleted_at is not null) as deleted_posts,
       countif(deleted_at is null and creation_method = 'AI_ASSISTED') as ai_assisted_posts,
       count(*) as raw_posts
from {{ ref('stg_posts') }}
group by post_type
