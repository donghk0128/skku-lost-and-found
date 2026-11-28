with per_run as (
    select r.id as run_id,
           r.algorithm_version,
           count(i.candidate_post_id) as item_count
    from {{ ref('stg_recommendation_runs') }} r
    left join {{ ref('stg_recommendation_items') }} i on r.id = i.run_id
    group by r.id, r.algorithm_version
)
select algorithm_version,
       count(*) as generated_runs,
       sum(item_count) as generated_items,
       round(avg(item_count), 1) as avg_items_per_run,
       countif(item_count = 0) as zero_item_runs
from per_run
group by algorithm_version
