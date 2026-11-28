select 'event_logs' as table_name, count(*) as row_count,
       max(received_at) as latest_source_at from {{ ref('stg_event_logs') }}
union all
select 'posts', count(*), max(updated_at) from {{ ref('stg_posts') }}
union all
select 'return_pairs', count(*), max(coalesce(confirmed_at, created_at))
from {{ ref('stg_return_pairs') }}
union all
select 'recommendation_runs', count(*), max(generated_at)
from {{ ref('stg_recommendation_runs') }}
union all
select 'recommendation_items', count(*), max(r.generated_at)
from {{ ref('stg_recommendation_items') }} i
left join {{ ref('stg_recommendation_runs') }} r on i.run_id = r.id
