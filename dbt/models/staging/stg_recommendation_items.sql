select run_id, candidate_post_id, rank, final_score, rule_score,
       semantic_score, text_score, category_score, time_score,
       location_score, color_conflict, distance_km, time_gap_hours
from {{ source('raw', 'recommendation_items') }}
