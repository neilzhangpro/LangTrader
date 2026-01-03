-- ============================================================
-- 迁移脚本: 扩展 risk_limits 风控硬约束配置
-- 版本: 006
-- 日期: 2026-01-02
-- 描述: 将 risk_limits 字段扩展为完整的风控配置结构
-- ============================================================

-- 更新 risk_limits 列的默认值（包含完整的风控参数）
-- 注意：这不会影响现有数据，只会影响新插入的记录
ALTER TABLE public.bots 
ALTER COLUMN risk_limits SET DEFAULT '{
    "max_total_exposure_pct": 0.8,
    "max_single_symbol_pct": 0.3,
    "max_leverage": 10,
    "max_consecutive_losses": 5,
    "max_daily_loss_pct": 0.05,
    "max_drawdown_pct": 0.15,
    "max_funding_rate_pct": 0.001,
    "funding_rate_check_enabled": true,
    "min_position_size_usd": 10.0,
    "max_position_size_usd": 10000.0,
    "min_risk_reward_ratio": 2.0,
    "hard_stop_enabled": true,
    "pause_on_consecutive_loss": true,
    "pause_on_max_drawdown": true
}'::jsonb;

-- 更新列注释
COMMENT ON COLUMN public.bots.risk_limits IS '风控硬约束配置 - 包含仓位控制、风险控制、资金费率控制、订单约束等参数';

-- ============================================================
-- 可选：更新现有记录的 risk_limits（合并新字段，保留原有配置）
-- 如果需要更新现有数据，取消下面的注释并执行
-- ============================================================

-- UPDATE public.bots 
-- SET risk_limits = risk_limits || '{
--     "max_leverage": 10,
--     "max_daily_loss_pct": 0.05,
--     "max_drawdown_pct": 0.15,
--     "max_funding_rate_pct": 0.001,
--     "funding_rate_check_enabled": true,
--     "min_position_size_usd": 10.0,
--     "max_position_size_usd": 10000.0,
--     "min_risk_reward_ratio": 2.0,
--     "hard_stop_enabled": true,
--     "pause_on_consecutive_loss": true,
--     "pause_on_max_drawdown": true
-- }'::jsonb
-- WHERE risk_limits IS NOT NULL;

-- ============================================================
-- 添加 system_configs 配置项说明（可选）
-- ============================================================

INSERT INTO public.system_configs (key, value, description, category)
VALUES 
    ('risk_limits.description', '风控硬约束配置说明', 
     '所有风控参数存储在 bots.risk_limits JSONB 字段中，执行节点会在下单前检查这些约束', 
     'documentation')
ON CONFLICT (key) DO NOTHING;

-- 添加各配置项的说明
INSERT INTO public.system_configs (key, value, description, category)
VALUES 
    ('risk_limits.max_total_exposure_pct', '0.8', '最大总敞口（占账户余额百分比）', 'risk'),
    ('risk_limits.max_single_symbol_pct', '0.3', '单币种最大敞口', 'risk'),
    ('risk_limits.max_leverage', '10', '最大杠杆倍数', 'risk'),
    ('risk_limits.max_consecutive_losses', '5', '连续亏损次数上限', 'risk'),
    ('risk_limits.max_daily_loss_pct', '0.05', '单日最大亏损', 'risk'),
    ('risk_limits.max_drawdown_pct', '0.15', '最大回撤', 'risk'),
    ('risk_limits.max_funding_rate_pct', '0.001', '最大资金费率', 'risk'),
    ('risk_limits.min_position_size_usd', '10', '最小开仓金额（USD）', 'risk'),
    ('risk_limits.max_position_size_usd', '10000', '最大开仓金额（USD）', 'risk'),
    ('risk_limits.min_risk_reward_ratio', '2.0', '最小风险回报比', 'risk')
ON CONFLICT (key) DO NOTHING;

