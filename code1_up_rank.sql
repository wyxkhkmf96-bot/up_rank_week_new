-- ============================================
-- up主榜单主表（全新UP版：首充≤29天 = 完整30天窗口）
-- ============================================

WITH
-- 步骤1: 近30天充电订单明细
-- ⚠️ 不能用此表做驱动，会丢失GMV=0的充电稿件
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

-- 步骤2: 全量充电视频清单（含GMV=0、state=0可见稿件，作为驱动表）
-- ✅ 顺带取出pubtime，避免up_recent_agg重复JOIN dim表
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
      --AND b.state = 0
),

-- 步骤3: UP首个充电视频发布日期
-- ⚠️ 不限state=0，避免遗漏已删除的早期充电稿件导致老UP被误判为全新UP
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

-- 步骤4: 近30日视频VV（avid+up_id粒度）
vv_recent_30d AS (
    SELECT
        up_id,
        avid,
        SUM(vv) AS vv
    FROM b_dwb.dwb_ctnt_arch_play_avid_mid_vv_vt_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
    GROUP BY 1,2
),

-- 步骤4a: 近30日视频播放UV（avid粒度）
-- ✅ cvr 分母用播放UV（看视频的人数），与稿件级(code3)口径对齐，避免用vv稀释
uv_recent_30d AS (
    SELECT
        avid,
        SUM(play_buvid_uv) AS play_uv
    FROM b_dwb.dwb_ctnt_arch_play_avid_vv_vt_i_d
    WHERE log_date BETWEEN b_current_datedelta('-30') AND b_current_datedelta('-1')
    GROUP BY 1
),

-- 步骤4b: 近30日视频GMV（avid+up_id粒度）
-- ✅ 必须先预聚合到视频粒度，否则订单明细直接JOIN会fan-out，
--    导致后续JOIN的vv被订单数重复加总而膨胀
gmv_recent_30d AS (
    SELECT
        up_id,
        avid,
        SUM(gmv) AS gmv
    FROM charge_order_30d
    GROUP BY 1,2
),

-- 步骤5: UP维度聚合
-- 驱动表为charge_video_list，保证GMV=0稿件不被丢失
-- charge_video_cnt口径：近30天新发布的充电稿件数（增量），直接用a.pubtime无需再JOIN dim表
-- ✅ 去重充电人数子查询加up_id范围限制，收窄扫描范围
-- ✅ GMV改用预聚合的gmv_recent_30d，与vv同为视频粒度1:1 JOIN，避免vv膨胀
-- ✅ play_uv 同为avid粒度聚合后JOIN，供cvr使用
up_recent_agg AS (
    SELECT
        a.up_id,
        COUNT(DISTINCT CASE WHEN a.pubtime >= DATE_SUB(CURRENT_DATE, 30) THEN a.avid ELSE NULL END) AS charge_video_cnt,
        SUM(COALESCE(b.gmv, 0)) AS gmv_30d,
        SUM(COALESCE(c.vv, 0)) AS vv_30d,
        SUM(COALESCE(e.play_uv, 0)) AS play_uv_30d,
        COALESCE(d.charge_users_30d, 0) AS charge_users_30d
    FROM charge_video_list a
    LEFT JOIN gmv_recent_30d b
        ON a.up_id = b.up_id AND a.avid = b.avid
    LEFT JOIN vv_recent_30d c
        ON a.up_id = c.up_id AND a.avid = c.avid
    LEFT JOIN uv_recent_30d e
        ON a.avid = e.avid
    LEFT JOIN (
        -- 跨稿件去重充电人数，✅ 限定有充电视频的UP主范围
        SELECT
            up_id,
            COUNT(DISTINCT mid) AS charge_users_30d
        FROM charge_order_30d
        WHERE up_id IN (SELECT up_id FROM charge_video_list)
        GROUP BY up_id
    ) d ON a.up_id = d.up_id
    GROUP BY 1, 6
),

-- 步骤6: UP基础信息
-- ✅ 提前过滤百万粉，减少后续JOIN数据量
-- ⚠️ avs_tid_name空分区存为''而非NULL，在SELECT层用CASE WHEN处理
up_info AS (
    SELECT
        up_id,
        nickname as uname,
        fans,
        avs_tid_name as tid_name,
        avs_sub_tid_name as sub_tid_name
    FROM b_ads.ads_prism_up_query_detail_1d_d
    WHERE log_date = b_current_datedelta('-1')
      AND fans < 1000000
)

-- 步骤7: 最终输出
SELECT
    a.up_id AS up_id,
    a.uname AS `up名`,
    a.fans AS `粉丝数`,
    -- ⚠️ 空字符串需单独判断，COALESCE无法处理''
    CASE WHEN a.tid_name IS NULL OR a.tid_name = '' THEN '未知' ELSE a.tid_name END AS `一级分区`,
    CASE WHEN a.sub_tid_name IS NULL OR a.sub_tid_name = '' THEN '未知' ELSE a.sub_tid_name END AS `二级分区`,
    CONCAT('https://space.bilibili.com/', a.up_id) AS `空间链接`,

    -- 首充信息
    b.first_charge_date AS `首充发布时间`,
    DATEDIFF(DATE_SUB(CURRENT_DATE, 1), b.first_charge_date) AS `首充距今天数`,

    -- 近30日充电稿件数（增量：近30天新发布）
    COALESCE(c.charge_video_cnt, 0) AS `近30日充电稿件数`,

    -- GMV指标
    ROUND(COALESCE(c.gmv_30d, 0), 0) AS `近30天gmv`,

    -- VV与转化指标
    COALESCE(c.vv_30d, 0) AS `近30日vv`,
    CASE
        WHEN COALESCE(c.vv_30d, 0) = 0 THEN 0
        ELSE ROUND(COALESCE(c.gmv_30d, 0) / NULLIF(c.vv_30d, 0) * 1000, 2)
    END AS `近30日ecpvv`,
    COALESCE(c.charge_users_30d, 0) AS `近30日充电人数`,
    -- cvr = 充电人数 / 播放UV（与稿件级口径一致），保留6位小数避免小值被抹0
    CASE
        WHEN COALESCE(c.play_uv_30d, 0) = 0 THEN 0
        ELSE ROUND(COALESCE(c.charge_users_30d, 0) / NULLIF(c.play_uv_30d, 0), 6)
    END AS `近30日cvr`

FROM up_info a
LEFT JOIN up_first_charge b ON a.up_id = b.up_id
LEFT JOIN up_recent_agg c ON a.up_id = c.up_id

-- 阈值：非百万粉已在up_info过滤，近30天GMV>1000，首充在近30天内（<=29=完整30天窗口）
WHERE c.gmv_30d > 1000
  AND DATEDIFF(DATE_SUB(CURRENT_DATE, 1), b.first_charge_date) <= 29

ORDER BY c.gmv_30d DESC
