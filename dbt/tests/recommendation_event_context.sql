select e.id
from {{ ref('stg_event_logs') }} e
left join {{ ref('stg_recommendation_runs') }} r on e.run_id = r.id
left join {{ ref('stg_recommendation_items') }} i
  on e.run_id = i.run_id and e.candidate_post_id = i.candidate_post_id
  and e.rank = i.rank
where e.event_type in ('recommendation_impression', 'recommendation_click')
  and (e.visit_id is null or e.source_post_id is null
       or r.id is null or r.source_post_id != e.source_post_id
       or i.run_id is null)
