-- One row per recorded impression or click; run generation itself is not exposure.
select e.id as event_id, e.event_type, date(e.occurred_at, 'Asia/Seoul') as event_date,
       e.occurred_at, e.visit_id, e.user_id, e.run_id, e.source_post_id,
       e.candidate_post_id, e.rank, r.algorithm_version
from {{ ref('stg_event_logs') }} e
join {{ ref('stg_recommendation_runs') }} r
  on e.run_id = r.id and e.source_post_id = r.source_post_id
join {{ ref('stg_recommendation_items') }} i
  on e.run_id = i.run_id and e.candidate_post_id = i.candidate_post_id
  and e.rank = i.rank
where e.event_type in ('recommendation_impression', 'recommendation_click')
