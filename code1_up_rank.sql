-- ============================================
-- up主榜单主表（全新UP版：首充≤30天）
-- ============================================

WITH
charge_order_30d AS (
    SELECT
        up_mid AS up_id,
        avid,
        mid,
        log_date,
        order_amt / 1000.0 AS gmv
    FROM bili_ogv.dwb_trd_main_chrg_order_p24h_ascrb_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
),
charge_video_list AS (
    SELECT DISTINCT
        a.mid AS up_id,
        a.aid AS avid
    FROM b_ods.ods_db2824_t_archive_a_hr a
    JOIN b_dim.dim_ctnt_arch_business_tag_info_d b
        ON a.aid = b.avid
    WHERE a.log_date = b_current_datedelta('-1')
      AND a.log_hour = '23'
      AND b.log_date = b_current_datedelta('-1')
      AND b.state = 0
),
up_first_charge AS (
    SELECT
        a.mid AS up_id,
        MIN(DATE(b.first_pub_time)) AS first_charge_date
    FROM b_ods.ods_db2824_t_archive_a_hr a
    JOIN b_dim.dim_ctnt_arch_business_tag_info_d b
        ON a.aid = b.avid
    WHERE a.log_date = b_current_datedelta('-1') AND a.log_hour = '23'
      AND b.log_date = b_current_datedelta('-1')
      AND b.first_pub_time IS NOT NULL
    GROUP BY 1
),
charge_recent_30d AS (
    SELECT
        up_id,
        avid,
        SUM(gmv) AS gmv_30d
    FROM charge_order_30d
    WHERE log_date >= b_current_datedelta('-30')
    GROUP BY 1,2
),
vv_recent_30d AS (
    SELECT
        up_id,
        avid,
        SUM(vv) AS vv
    FROM b_dwb.dwb_ctnt_arch_play_avid_mid_vv_vt_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
    GROUP BY 1,2
),
up_recent_agg AS (
    SELECT
        a.up_id,
        COUNT(DISTINCT a.avid) AS charge_video_cnt,
        SUM(COALESCE(b.gmv_30d, 0)) AS gmv_30d,
        SUM(COALESCE(c.vv, 0)) AS vv_30d,
        COALESCE(d.charge_users_30d, 0) AS charge_users_30d
    FROM charge_video_list a
    LEFT JOIN charge_recent_30d b
        ON a.up_id = b.up_id AND a.avid = b.avid
    LEFT JOIN vv_recent_30d c
        ON a.up_id = c.up_id AND a.avid = c.avid
    LEFT JOIN (
        SELECT
            up_id,
            COUNT(DISTINCT mid) AS charge_users_30d
        FROM charge_order_30d
        WHERE log_date >= b_current_datedelta('-30')
        GROUP BY up_id
    ) d ON a.up_id = d.up_id
    GROUP BY 1, 5
),
up_info AS (
    SELECT
        up_id,
        nickname as uname,
        fans,
        avs_tid_name as tid_name,
        avs_sub_tid_name as sub_tid_name
    FROM b_ads.ads_prism_up_query_detail_1d_d
    WHERE log_date = b_current_datedelta('-1')
)

SELECT
    a.up_id AS up_id,
    a.uname AS `up名`,
    a.fans AS `粉丝数`,
    COALESCE(a.tid_name, '未知') AS `一级分区`,
    COALESCE(a.sub_tid_name,'未知') AS `二级分区`,
    CONCAT('https://space.bilibili.com/', a.up_id) AS `空间链接`,
    b.first_charge_date AS `首充发布时间`,
    DATEDIFF(DATE_SUB(CURRENT_DATE, 1), b.first_charge_date) AS `首充距今天数`,
    COALESCE(c.charge_video_cnt, 0) AS `近30日充电稿件数`,
    ROUND(COALESCE(c.gmv_30d, 0), 0) AS `近30天gmv`,
    ROUND(COALESCE(c.gmv_30d, 0) / NULLIF(DATEDIFF(DATE_SUB(CURRENT_DATE, 1), b.first_charge_date), 0), 2) AS `首充距今日均gmv`,
    ROUND(COALESCE(c.gmv_30d, 0) / 30, 2) AS `近30日日均gmv`,
    COALESCE(c.vv_30d, 0) AS `近30日vv`,
    CASE
        WHEN COALESCE(c.vv_30d, 0) = 0 THEN 0
        ELSE ROUND(COALESCE(c.gmv_30d, 0) / NULLIF(c.vv_30d, 0) * 1000, 2)
    END AS `近30日ecpvv`,
    COALESCE(c.charge_users_30d, 0) AS `近30日充电人数`,
    CASE
        WHEN COALESCE(c.vv_30d, 0) = 0 THEN 0
        ELSE ROUND(COALESCE(c.charge_users_30d, 0) / NULLIF(c.vv_30d, 0), 4)
    END AS `近30日cvr`
FROM up_info a
LEFT JOIN up_first_charge b
    ON a.up_id = b.up_id
LEFT JOIN up_recent_agg c
    ON a.up_id = c.up_id
WHERE c.gmv_30d > 1000
  AND a.fans < 1000000
  AND DATEDIFF(DATE_SUB(CURRENT_DATE, 1), b.first_charge_date) <= 30
ORDER BY c.gmv_30d DESC
