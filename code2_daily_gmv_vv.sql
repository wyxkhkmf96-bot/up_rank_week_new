WITH
charge_daily AS (
    SELECT
        up_mid AS up_id,
        log_date AS dt,
        SUM(order_amt) / 1000.0 AS daily_gmv
    FROM bili_ogv.dwb_trd_main_chrg_order_p24h_ascrb_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') and b_current_datedelta('-1')
    GROUP BY 1,2
),
charge_video_list AS (
    SELECT DISTINCT
        a.mid AS up_id,
        a.aid AS avid
    FROM b_ods.ods_db2824_t_archive_a_hr a
    INNER JOIN b_dim.dim_ctnt_arch_business_tag_info_d b
        ON a.aid = b.avid
    WHERE a.log_date = b_current_datedelta('-1')
      AND a.log_hour = '23'
      AND b.log_date = b_current_datedelta('-1')
      AND b.state = 0
),
vv_daily AS (
    SELECT
        a.up_id,
        a.log_date AS dt,
        SUM(a.vv) AS daily_vv
    FROM b_dwb.dwb_ctnt_arch_play_avid_mid_vv_vt_i_d a
    INNER JOIN charge_video_list b
        ON a.up_id = b.up_id
        AND a.avid = b.avid
    WHERE log_date between b_current_datedelta('-30') and b_current_datedelta('-1')
    GROUP BY 1,2
)
SELECT
    COALESCE(a.up_id, b.up_id) AS `up_id`,
    COALESCE(a.dt, b.dt) AS `日期`,
    COALESCE(a.daily_gmv, 0) AS `gmv`,
    COALESCE(b.daily_vv, 0) AS `vv`
FROM charge_daily a
FULL OUTER JOIN vv_daily b
    ON a.up_id = b.up_id
    AND a.dt = b.dt
WHERE COALESCE(a.up_id, b.up_id) IN ({IN_CLAUSE})
