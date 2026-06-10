-- ============================================
-- 黑马UP榜单主表（老充电UP：近30天GMV环比增速≥50% 且非堆量驱动）
-- ============================================

WITH
-- 步骤1: 近60天充电订单明细（同时覆盖近30/前30两个窗口）
charge_order_60d AS (
    SELECT
        up_mid as up_id,
        avid,
        mid,
        log_date,
        order_amt / 1000.0 AS gmv
    FROM bili_ogv.dwb_trd_main_chrg_order_p24h_ascrb_i_d
    WHERE log_date between b_current_datedelta('-60') and b_current_datedelta('-1')
),

-- 步骤2: 充电视频清单（近60天发布 + state=0可见稿件，作为驱动表）
-- ✅ 限定 pubtime 近60天，与近30/前30区间对齐，避免历史全量膨胀
charge_video_list AS (
    SELECT DISTINCT
        a.mid AS up_id,
        a.aid AS avid,
        b.pubtime
    FROM b_ods.ods_db2824_t_archive_a_hr a
    JOIN b_dim.dim_ctnt_arch_business_tag_info_d b
        ON a.aid = b.avid
    WHERE a.log_date = b_current_datedelta('-1')
      AND a.log_hour = '23'
      AND b.log_date = b_current_datedelta('-1')
      AND b.state = 0
      AND b.pubtime >= DATE_SUB(CURRENT_DATE, 60)
      AND b.pubtime < CURRENT_DATE
),

-- 步骤3: UP首个充电视频发布日期
-- ⚠️ 不限state=0和pubtime，避免遗漏已删除早期充电稿件导致老UP被误判为全新
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

-- 步骤4: 近30日视频VV
vv_recent_30d AS (
    SELECT
        up_id,
        avid,
        SUM(vv) AS vv
    FROM b_dwb.dwb_ctnt_arch_play_avid_mid_vv_vt_i_d
    WHERE log_date between b_current_datedelta('-30') and b_current_datedelta('-1')
    GROUP BY up_id, avid
),

-- 步骤4a: 近30日视频播放UV（avid粒度）
-- ✅ cvr 分母用播放UV（看视频的人数），与稿件级(code3)口径对齐，避免用vv稀释
uv_recent_30d AS (
    SELECT
        avid,
        SUM(play_buvid_uv) AS play_uv
    FROM b_dwb.dwb_ctnt_arch_play_avid_vv_vt_i_d
    WHERE log_date between b_current_datedelta('-30') and b_current_datedelta('-1')
    GROUP BY 1
),

-- 步骤5a: 视频粒度GMV聚合（近30/前30一次扫描）
-- ✅ 预聚合到(up_id, avid)粒度，避免后续JOIN VV时被订单数fan-out放大
-- ✅ 前置up_id范围过滤，减少预聚合数据量
charge_video_gmv AS (
    SELECT
        up_id,
        avid,
        SUM(CASE WHEN log_date >= b_current_datedelta('-30') THEN gmv ELSE 0 END) AS gmv_30d,
        SUM(CASE WHEN log_date <  b_current_datedelta('-30') THEN gmv ELSE 0 END) AS gmv_prev30d
    FROM charge_order_60d
    WHERE up_id IN (SELECT up_id FROM charge_video_list)
    GROUP BY 1, 2
),

-- 步骤5b: UP维度聚合
-- ✅ GROUP BY 只按 up_id，charge_users_30d 改用 MAX 避免fan-out产生多行
-- ✅ 删除冗余字段 charge_video_cnt_60d（SELECT未使用）
up_agg AS (
    SELECT
        a.up_id,
        SUM(COALESCE(g.gmv_30d, 0))      AS gmv_30d,
        SUM(COALESCE(g.gmv_prev30d, 0))  AS gmv_prev30d,
        SUM(COALESCE(c.vv, 0))           AS vv_30d,
        SUM(COALESCE(e.play_uv, 0))      AS play_uv_30d,
        MAX(COALESCE(d.charge_users_30d, 0)) AS charge_users_30d
    FROM charge_video_list a
    LEFT JOIN charge_video_gmv g
        ON a.up_id = g.up_id AND a.avid = g.avid
    LEFT JOIN vv_recent_30d c
        ON a.up_id = c.up_id AND a.avid = c.avid
    LEFT JOIN uv_recent_30d e
        ON a.avid = e.avid
    LEFT JOIN (
        -- 跨稿件去重充电人数，限定有充电视频的UP主范围
        SELECT
            up_id,
            COUNT(DISTINCT mid) AS charge_users_30d
        FROM charge_order_60d
        WHERE log_date >= b_current_datedelta('-30')
          AND up_id IN (SELECT up_id FROM charge_video_list)
        GROUP BY up_id
    ) d ON a.up_id = d.up_id
    GROUP BY a.up_id
),

-- 步骤6: 近30/前30日充电发稿数
-- ✅ 直接用charge_video_list.pubtime，无需再JOIN dim表
pub_cnt_agg AS (
    SELECT
        up_id,
        COUNT(DISTINCT CASE WHEN pubtime >= DATE_SUB(CURRENT_DATE, 30) AND pubtime < CURRENT_DATE
                            THEN avid END) AS recent_30d_pub_cnt,
        COUNT(DISTINCT CASE WHEN pubtime >= DATE_SUB(CURRENT_DATE, 60) AND pubtime < DATE_SUB(CURRENT_DATE, 30)
                            THEN avid END) AS prev_30d_pub_cnt
    FROM charge_video_list
    GROUP BY 1
),

-- 步骤7: UP基础信息（提前过滤百万粉，减少后续JOIN数据量）
up_info AS (
    SELECT
        up_id,
        nickname AS uname,
        fans,
        avs_tid_name AS tid_name,
        avs_sub_tid_name AS sub_tid_name
    FROM b_ads.ads_prism_up_query_detail_1d_d
    WHERE log_date = b_current_datedelta('-1')
      AND fans < 1000000
)

SELECT
    a.up_id as up_id,
    a.uname as `up名`,
    a.fans as `粉丝数`,
    CASE WHEN a.tid_name IS NULL OR a.tid_name = '' THEN '未知' ELSE a.tid_name END as `一级分区`,
    CASE WHEN a.sub_tid_name IS NULL OR a.sub_tid_name = '' THEN '未知' ELSE a.sub_tid_name END as `二级分区`,
    CONCAT('https://space.bilibili.com/', a.up_id) as `空间链接`,

    -- 首充信息
    b.first_charge_date as `首充发布时间`,
    DATEDIFF(date_sub(current_date, 1), b.first_charge_date) as `首充距今天数`,
    CASE
        WHEN DATEDIFF(date_sub(current_date, 1), b.first_charge_date) <= 29 THEN '全新'
        ELSE '成长'
    END AS `榜单类型`,
    -- 充电稿件数/发稿数（近30天口径，同一字段）
    COALESCE(p.recent_30d_pub_cnt, 0) AS `近30日充电稿件数`,
    COALESCE(p.prev_30d_pub_cnt, 0) AS `前30日充电稿件数`,
    CASE
        WHEN COALESCE(p.prev_30d_pub_cnt, 0) = 0 THEN 0
        ELSE ROUND((COALESCE(p.recent_30d_pub_cnt, 0) * 1.0 / p.prev_30d_pub_cnt) - 1, 4)
    END AS `稿件数增速`,

    -- GMV指标
    round(COALESCE(c.gmv_30d, 0), 0) AS `近30天gmv`,
    round(COALESCE(c.gmv_prev30d, 0), 0) AS `前30天gmv`,
    -- 30天环比增速（总量比口径，与WHERE筛选一致）
    CASE
        WHEN COALESCE(c.gmv_prev30d, 0) = 0 THEN 0
        ELSE round((COALESCE(c.gmv_30d, 0) - COALESCE(c.gmv_prev30d, 0)) / c.gmv_prev30d, 4)
    END AS `30天环比增速`,

    -- VV与转化指标
    COALESCE(c.vv_30d, 0) AS `近30日vv`,
    CASE
        WHEN COALESCE(c.vv_30d, 0) = 0 THEN 0
        ELSE round(COALESCE(c.gmv_30d, 0) / NULLIF(c.vv_30d, 0) * 1000, 2)
    END AS `近30日ecpvv`,
    COALESCE(c.charge_users_30d, 0) AS `近30日充电人数`,
    -- cvr = 充电人数 / 播放UV（与稿件级口径一致），保留6位小数避免小值被抹0
    CASE
        WHEN COALESCE(c.play_uv_30d, 0) = 0 THEN 0
        ELSE round(COALESCE(c.charge_users_30d, 0) / NULLIF(c.play_uv_30d, 0), 6)
    END AS `近30日cvr`

FROM up_info a
LEFT JOIN up_first_charge b ON a.up_id = b.up_id
LEFT JOIN up_agg c ON a.up_id = c.up_id
LEFT JOIN pub_cnt_agg p ON a.up_id = p.up_id

  -- 类② 筛选：稿件量持平 + GMV显著提升
  -- 基本条件：是充电老up，且前30日gmv>1000
WHERE DATEDIFF(date_sub(current_date, 1), b.first_charge_date) > 29
  AND c.gmv_prev30d > 1000
  -- 近30天有发稿
  AND COALESCE(p.recent_30d_pub_cnt, 0) >= 1
  -- 前30天有发稿（避免除零）
  AND COALESCE(p.prev_30d_pub_cnt, 0) > 0
  -- GMV增速≥50%
  AND (COALESCE(c.gmv_30d, 0) - c.gmv_prev30d) / c.gmv_prev30d >= 0.5
  -- 稿件增速 < GMV增速
  AND (p.recent_30d_pub_cnt - p.prev_30d_pub_cnt) * 1.0 / p.prev_30d_pub_cnt
      < (c.gmv_30d - c.gmv_prev30d) / c.gmv_prev30d
  -- 稿件量基本持平：变化≤2篇 或 变化幅度≤20%
  --AND (
  --    ABS(p.recent_30d_pub_cnt - p.prev_30d_pub_cnt) <= 2
  --    OR ABS(p.recent_30d_pub_cnt - p.prev_30d_pub_cnt) * 1.0 / p.prev_30d_pub_cnt <= 0.20
  --)

ORDER BY `30天环比增速` DESC
