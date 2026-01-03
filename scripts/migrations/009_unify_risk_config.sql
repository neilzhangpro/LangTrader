-- ============================================================
-- 迁移脚本: 统一风控配置，清理冗余字段
-- 版本: 009
-- 日期: 2026-01-03
-- 描述: 
--   1. 删除 system_configs 中与 bots.risk_limits 重复的配置
--   2. 更新 bots.risk_limits 默认值，新增字段
--   3. 添加配置命名映射注释
-- ============================================================

-- ============================================================
-- Part 1: 删除 system_configs 中冗余的风控配置
-- 这些配置现在统一从 bots.risk_limits 读取
-- ============================================================

DELETE FROM system_configs WHERE config_key IN (
    'batch_decision.max_total_allocation_pct',
    'batch_decision.max_single_allocation_pct',
    'batch_decision.min_cash_reserve_pct'
);

-- 保留 batch_decision.timeout_seconds，这是节点运行时配置
-- 保留 debate.timeout_per_round，这是节点运行时配置

-- ============================================================
-- Part 2: 更新 bots.risk_limits 默认值
-- 新增字段：max_total_positions, default_leverage
-- ============================================================

ALTER TABLE public.bots 
ALTER COLUMN risk_limits SET DEFAULT '{
    "max_total_allocation_pct": 80.0,
    "max_single_allocation_pct": 30.0,
    "max_leverage": 10,
    "default_leverage": 3,
    "max_total_positions": 5,
    "max_consecutive_losses": 5,
    "max_daily_loss_pct": 5.0,
    "max_drawdown_pct": 15.0,
    "max_funding_rate_pct": 0.1,
    "funding_rate_check_enabled": true,
    "min_position_size_usd": 10.0,
    "max_position_size_usd": 10000.0,
    "min_risk_reward_ratio": 2.0,
    "hard_stop_enabled": true,
    "pause_on_consecutive_loss": true,
    "pause_on_max_drawdown": true
}'::jsonb;

-- ============================================================
-- Part 3: 更新现有 Bot 的 risk_limits（合并新字段）
-- ============================================================

UPDATE public.bots 
SET risk_limits = COALESCE(risk_limits, '{}'::jsonb) || jsonb_build_object(
    'max_total_allocation_pct', COALESCE((risk_limits->>'max_total_exposure_pct')::float * 100, 80.0),
    'max_single_allocation_pct', COALESCE((risk_limits->>'max_single_symbol_pct')::float * 100, 30.0),
    'max_total_positions', COALESCE((risk_limits->>'max_total_positions')::int, 5),
    'default_leverage', COALESCE((risk_limits->>'default_leverage')::int, 3),
    'max_daily_loss_pct', COALESCE((risk_limits->>'max_daily_loss_pct')::float * 100, 5.0),
    'max_drawdown_pct', COALESCE((risk_limits->>'max_drawdown_pct')::float * 100, 15.0),
    'max_funding_rate_pct', COALESCE((risk_limits->>'max_funding_rate_pct')::float * 100, 0.1)
)
WHERE risk_limits IS NOT NULL;

-- ============================================================
-- Part 4: 添加配置说明注释
-- ============================================================

COMMENT ON COLUMN public.bots.risk_limits IS '
风控硬约束配置（唯一配置源）
============================

仓位控制:
  - max_total_allocation_pct: 最大总仓位百分比 (默认 80%)
  - max_single_allocation_pct: 单币种最大仓位百分比 (默认 30%)
  - max_leverage: 最大杠杆倍数 (默认 10)
  - default_leverage: 默认杠杆倍数 (默认 3)
  - max_total_positions: 最大持仓数量 (默认 5)

订单约束:
  - min_position_size_usd: 最小开仓金额 USD (默认 10)
  - max_position_size_usd: 最大开仓金额 USD (默认 10000)
  - min_risk_reward_ratio: 最小风险回报比 (默认 2.0)

风险控制:
  - max_consecutive_losses: 最大连续亏损次数 (默认 5)
  - max_daily_loss_pct: 单日最大亏损百分比 (默认 5%)
  - max_drawdown_pct: 最大回撤百分比 (默认 15%)
  - max_funding_rate_pct: 最大资金费率百分比 (默认 0.1%)

开关控制:
  - funding_rate_check_enabled: 启用资金费率检查 (默认 true)
  - hard_stop_enabled: 启用硬止损 (默认 true)
  - pause_on_consecutive_loss: 连续亏损时暂停 (默认 true)
  - pause_on_max_drawdown: 触及最大回撤时暂停 (默认 true)

注意：所有百分比值现在统一使用百分比格式（如 80 表示 80%），不再使用小数格式。
';

-- 标记废弃的独立字段
COMMENT ON COLUMN public.bots.max_position_size_percent IS '⚠️ 已废弃：请使用 risk_limits.max_single_allocation_pct';
COMMENT ON COLUMN public.bots.max_total_positions IS '⚠️ 已废弃：请使用 risk_limits.max_total_positions';
COMMENT ON COLUMN public.bots.max_leverage IS '⚠️ 已废弃：请使用 risk_limits.max_leverage';

-- ============================================================
-- Part 5: 验证迁移结果
-- ============================================================

SELECT '✅ Risk Config Unified Migration Complete' AS status;

-- 显示删除的配置数量
SELECT 'Deleted redundant system_configs' AS action, 
       COUNT(*) AS deleted_count 
FROM system_configs 
WHERE config_key LIKE 'batch_decision.max_%' 
   OR config_key = 'batch_decision.min_cash_reserve_pct';

-- 显示现有 Bot 的 risk_limits 配置
SELECT id, name, 
       risk_limits->>'max_total_allocation_pct' AS max_total_pct,
       risk_limits->>'max_single_allocation_pct' AS max_single_pct,
       risk_limits->>'min_position_size_usd' AS min_size_usd,
       risk_limits->>'max_position_size_usd' AS max_size_usd
FROM bots 
LIMIT 3;


