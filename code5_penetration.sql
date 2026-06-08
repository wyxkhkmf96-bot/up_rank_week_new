WITH premiere_avids AS (
    SELECT DISTINCT aid AS avid
    FROM b_ods.ods_db2824_t_archive_a_hr
    WHERE log_date = b_current_datedelta('-1')
      AND log_hour = '23'
),
up_info AS (
    SELECT DISTINCT
        up_id,
        avs_tid_name as tid_name,
        avs_sub_tid_name as sub_tid_name
    FROM b_ads.ads_prism_up_query_detail_1d_d
    WHERE log_date = b_current_datedelta('-1')
)
SELECT
    CASE WHEN GROUPING(u.tid_name) = 1 THEN 'all'
     WHEN u.tid_name IS NULL OR u.tid_name = '' THEN '未知'
     ELSE u.tid_name END AS `一级分区`,
    CASE WHEN GROUPING(u.sub_tid_name) = 1 THEN 'all'
     WHEN u.sub_tid_name IS NULL OR u.sub_tid_name = '' THEN '未知'
     ELSE u.sub_tid_name END AS `二级分区`,
    COUNT(DISTINCT a.avid) AS `近30日总稿件数`,
    COUNT(DISTINCT CASE WHEN a.is_charging_pay = 1 OR b.avid IS NOT NULL THEN a.avid ELSE NULL END) AS `近30日充电稿件数`,
    ROUND(
        COUNT(DISTINCT CASE WHEN a.is_charging_pay = 1 OR b.avid IS NOT NULL THEN a.avid ELSE NULL END) * 1.0 /
        NULLIF(COUNT(DISTINCT a.avid), 0),
        6
    ) AS `充电渗透率`,
    COUNT(DISTINCT a.up_id) AS `近30日总UP主数`,
    COUNT(DISTINCT CASE WHEN a.is_charging_pay = 1 OR b.avid IS NOT NULL THEN a.up_id ELSE NULL END) AS `近30日有充电的UP主数`
FROM b_dim.dim_ctnt_arch_business_tag_info_d a
LEFT JOIN premiere_avids b ON a.avid = b.avid
LEFT JOIN up_info u ON a.up_id = u.up_id
WHERE a.log_date = b_current_datedelta('-1')
  AND a.first_pub_time BETWEEN DATE_SUB(CURRENT_DATE, 30) AND DATE_SUB(CURRENT_DATE, 1)
  --AND a.state = 0
GROUP BY u.tid_name, u.sub_tid_name
GROUPING SETS (
    (u.tid_name, u.sub_tid_name),
    (u.tid_name),
    ()
)
