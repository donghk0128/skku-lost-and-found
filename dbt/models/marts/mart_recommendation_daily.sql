select event_date,
       countif(event_type = 'recommendation_impression') as impressions,
       countif(event_type = 'recommendation_click') as clicks,
       safe_divide(countif(event_type = 'recommendation_click'),
                   countif(event_type = 'recommendation_impression')) as click_per_impression
from {{ ref('int_recommendation_events') }}
group by 1
