-- ============================================================
-- 迁移脚本: 更新 risk_limits 默认值
-- 版本: 012
-- 日期: 2026-01-11
-- 描述:
--   1. 更新 bots.risk_limits 列的默认值（使用推荐配置）
--   2. 关键修改：max_funding_rate_pct 从 0.001/0.1 改为 0.05
--   3. 更新现有 Bot 的资金费率配置（如果仍使用旧的过严值）
-- ============================================================

-- ============================================================
-- Part 1: 更新列默认值
-- ============================================================

ALTER TABLE public.bots
ALTER COLUMN risk_limits SET DEFAULT '{
    "max_total_allocation_pct": 80,
    "max_single_allocation_pct": 30,
    "max_total_exposure_pct": 0.8,
    "max_single_symbol_pct": 0.3,
    "max_leverage": 5,
    "default_leverage": 3,
    "max_total_positions": 5,
    "max_consecutive_losses": 5,
    "max_daily_loss_pct": 5,
    "max_drawdown_pct": 15,
    "max_funding_rate_pct": 0.05,
    "funding_rate_check_enabled": true,
    "min_position_size_usd": 10.0,
    "max_position_size_usd": 5000.0,
    "min_risk_reward_ratio": 2.0,
    "hard_stop_enabled": true,
    "pause_on_consecutive_loss": true,
    "pause_on_max_drawdown": true,
    "trailing_stop_enabled": false,
    "trailing_stop_trigger_pct": 3.0,
    "trailing_stop_distance_pct": 1.5,
    "trailing_stop_lock_profit_pct": 1.0
}'::jsonb;

-- ============================================================
-- Part 2: 修复现有 Bot 的过严资金费率配置
-- 如果 max_funding_rate_pct <= 0.01，更新为 0.05
-- ============================================================

UPDATE public.bots
SET risk_limits = risk_limits || jsonb_build_object(
    'max_funding_rate_pct', 0.05
)
WHERE risk_limits IS NOT NULL
  AND (
    (risk_limits->>'max_funding_rate_pct')::float <= 0.01
    OR risk_limits->>'max_funding_rate_pct' IS NULL
  );

-- ============================================================
-- Part 3: 更新其他推荐值（可选，保守执行）
-- ============================================================

-- 更新 max_position_size_usd 为 5000（如果当前是 10000）
UPDATE public.bots
SET risk_limits = risk_limits || jsonb_build_object(
    'max_position_size_usd', 5000.0
)
WHERE risk_limits IS NOT NULL
  AND (risk_limits->>'max_position_size_usd')::float >= 10000;

-- 更新 max_leverage 为 5（如果当前是 10 或更高）
UPDATE public.bots
SET risk_limits = risk_limits || jsonb_build_object(
    'max_leverage', 5
)
WHERE risk_limits IS NOT NULL
  AND (risk_limits->>'max_leverage')::int >= 10;

-- ============================================================
-- Part 4: 验证迁移结果
-- ============================================================

SELECT '✅ Risk limits defaults updated' AS status;

-- 显示更新后的 Bot 配置
SELECT id, name,
       risk_limits->>'max_funding_rate_pct' AS funding_rate_pct,
       risk_limits->>'max_position_size_usd' AS max_size_usd,
       risk_limits->>'max_leverage' AS max_leverage,
       risk_limits->>'max_total_allocation_pct' AS max_total_pct
FROM bots
LIMIT 5;
