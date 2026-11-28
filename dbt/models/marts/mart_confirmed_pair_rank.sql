-- A pair may be absent from runs. This is coverage among labelled runs, not service recall.
select p.id as pair_id, r.id as run_id, r.algorithm_version,
       r.generated_at, min(i.rank) as matched_rank
from {{ ref('int_confirmed_pairs') }} p
join {{ ref('stg_recommendation_runs') }} r
  on r.source_post_id in (p.lost_post_id, p.found_post_id)
left join {{ ref('stg_recommendation_items') }} i
  on i.run_id = r.id
  and i.candidate_post_id = if(r.source_post_id = p.lost_post_id,
                               p.found_post_id, p.lost_post_id)
group by 1, 2, 3, 4
