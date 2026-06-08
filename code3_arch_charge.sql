WITH premiere_avids AS (
    SELECT DISTINCT aid AS avid
    FROM b_ods.ods_db2824_t_archive_a_hr
    WHERE log_date = b_current_datedelta('-1')
      AND log_hour = '23'
      AND archive_config LIKE '%members_premiere%'
),
arch_info AS (
    SELECT
        a.avid,
        a.up_id,
        a.uname,
        a.title,
        a.pubtime,
        a.tid_name,
        a.sub_tid_name,
        a.tag,
        CASE
            WHEN b.avid IS NOT NULL AND a.is_charging_pay = 1 THEN '抢先看(进行中)'
            WHEN b.avid IS NOT NULL AND a.is_charging_pay = 0 THEN '抢先看(已到期转免费)'
            ELSE '充电稿件'
        END AS arch_type
    FROM b_dim.dim_ctnt_arch_business_tag_info_d a
    LEFT JOIN premiere_avids b ON a.avid = b.avid
    WHERE a.log_date = b_current_datedelta('-1')
      --and a.state = 0
      AND (a.is_charging_pay = 1 OR b.avid IS NOT NULL)
      AND a.up_id IN ({IN_CLAUSE})
      AND a.pubtime >= DATE_SUB(CURRENT_DATE, 30)
),
charge_revenue AS (
    SELECT
        avid,
        SUM(order_amt) AS total_gmv,
        COUNT(DISTINCT mid) AS charge_users
    FROM bili_ogv.dwb_trd_main_chrg_order_p24h_ascrb_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
    GROUP BY 1
),
play_stats AS (
    SELECT
        avid,
        SUM(vv) AS total_vv,
        SUM(play_buvid_uv) AS total_play_uv
    FROM b_dwb.dwb_ctnt_arch_play_avid_vv_vt_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
    GROUP BY 1
),
asr_content AS (
    SELECT
        aid AS avid,
        MIN(asr_data) AS asr_data
    FROM ai.llm_asr_filter_full
    WHERE log_date = b_current_datedelta('-1')
      AND aid IN (SELECT avid FROM arch_info)
    GROUP BY 1
)
SELECT
    a.up_id AS `UP主ID`,
    a.uname AS `UP主昵称`,
    a.avid as `稿件ID`,
    a.title AS `稿件标题`,
    a.arch_type AS `稿件类型`,
    CONCAT('https://www.bilibili.com/video/av', a.avid) AS `播放页`,
    a.pubtime AS `发布时间`,
    a.tid_name AS `一级分区`,
    a.sub_tid_name AS `二级分区`,
    a.tag as `tag`,
    ROUND(COALESCE(b.total_gmv, 0) / 1000.0, 2) AS `稿件近30日GMV`,
    COALESCE(c.total_vv, 0) AS `稿件近30日播放量`,
    ROUND(COALESCE(b.total_gmv, 0) / NULLIF(c.total_vv, 0) * 1000 / 1000.0, 2) AS `稿件近30日ECPVV`,
    COALESCE(b.charge_users, 0) AS `稿件近30日充电人数`,
    ROUND(COALESCE(b.charge_users, 0) / NULLIF(c.total_play_uv, 0), 4) AS `稿件近30日转化率`,
    SUBSTRING(d.asr_data, 1, 1000) AS asr_data
FROM arch_info a
LEFT JOIN charge_revenue b ON a.avid = b.avid
LEFT JOIN play_stats c ON a.avid = c.avid
LEFT JOIN asr_content d ON a.avid = d.avid
WHERE b.total_gmv > 0
ORDER BY b.total_gmv DESC
