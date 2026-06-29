-- ============================================
-- 近30天UP主日维度充电GMV + 充电视频VV
-- ============================================

WITH 
-- ============================================
-- 步骤1: 充电订单日维度聚合（GMV）
-- ============================================
charge_daily AS (
    SELECT
        up_mid AS up_id,
        log_date AS dt,
        SUM(order_amt) / 1000.0 AS daily_gmv
    FROM bili_ogv.dwb_trd_main_chrg_order_p24h_ascrb_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
      AND up_mid IN ({IN_CLAUSE})
    GROUP BY 1, 2
),

-- ============================================
-- 步骤2: 充电视频日维度VV聚合
-- ============================================
vv_daily AS (
    SELECT
        a.up_id,
        a.log_date AS dt,
        SUM(a.vv) AS daily_vv
    FROM b_dwb.dwb_ctnt_arch_play_avid_mid_vv_vt_i_d a
    INNER JOIN b_ods.ods_db2824_t_archive_a_hr b
        ON a.avid = b.aid
        AND a.up_id = b.mid
    WHERE a.log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
          AND b.log_date = b_current_datedelta('-1')
          AND b.log_hour = '23'
          AND a.up_id IN ({IN_CLAUSE})
          and b.mid in ({IN_CLAUSE})
    GROUP BY 1, 2
)

-- ============================================
-- 步骤3: 组装输出（UP × 日期 粒度）
-- 注意：用FULL OUTER JOIN确保GMV和VV都有数据的日期都出现
-- ============================================
SELECT
    up_id,
    dt AS `日期`,
    SUM(gmv) AS `gmv`,
    SUM(vv) AS `vv`
FROM (
    SELECT up_id, dt, daily_gmv AS gmv, 0 AS vv FROM charge_daily
    UNION ALL
    SELECT up_id, dt, 0 AS gmv, daily_vv AS vv FROM vv_daily
) t
GROUP BY up_id, dt
