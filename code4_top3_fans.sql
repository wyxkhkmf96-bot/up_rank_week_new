WITH base_data AS (
    SELECT
        up_id,
        uname,
        same_tid_up_concat_value
    FROM b_ads.ads_prty_creator_semi_up_coincide_1d_d
    WHERE log_date = b_current_datedelta('-1')
      AND up_id IN ({IN_CLAUSE})
      AND user_type = 'fans'
),
top3_ups AS (
    SELECT
        up_id,
        uname,
        similar_up_id,
        fans_overlap,
        rn
    FROM (
        SELECT
            up_id,
            uname,
            CAST(key AS BIGINT) AS similar_up_id,
            value AS fans_overlap,
            ROW_NUMBER() OVER(PARTITION BY up_id ORDER BY value DESC) AS rn
        FROM base_data
        LATERAL VIEW EXPLODE(same_tid_up_concat_value) t AS key, value
    ) tmp
    WHERE rn <= 3
),
up_names AS (
    SELECT DISTINCT
        up_id,
        nickname
    FROM b_ads.ads_prism_up_query_detail_1d_d
    WHERE log_date = b_current_datedelta('-1')
      AND up_id IN (SELECT similar_up_id FROM top3_ups)
)
SELECT
    t.up_id AS `UP主ID`,
    t.uname AS `UP主昵称`,
    MAP_FROM_ENTRIES(
        COLLECT_LIST(
            STRUCT(CAST(t.similar_up_id AS STRING), t.fans_overlap)
        )
    ) AS `Top3共粉UP共粉数`,
    ARRAY_JOIN(
        COLLECT_LIST(u.nickname),
        ','
    ) AS `Top3共粉UP昵称`
FROM top3_ups t
LEFT JOIN up_names u ON t.similar_up_id = u.up_id
GROUP BY t.up_id, t.uname
ORDER BY t.up_id
