select p.id
from {{ ref('int_confirmed_pairs') }} p
left join {{ ref('stg_posts') }} lost on lost.id = p.lost_post_id
left join {{ ref('stg_posts') }} found on found.id = p.found_post_id
where lost.id is null or found.id is null
   or lost.post_type != 'LOST' or found.post_type != 'FOUND'
