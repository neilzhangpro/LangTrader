-- ============================================================
-- 迁移脚本: 删除 bots 表中废弃的独立字段
-- 版本: 010
-- 日期: 2026-01-03
-- 描述: 
--   删除 max_leverage, max_position_size_percent, 
--   max_total_positions, max_concurrent_symbols 字段
--   这些配置现在统一从 risk_limits JSONB 字段读取
-- ============================================================

-- ============================================================
-- Part 1: 备份现有数据到 risk_limits（如果尚未迁移）
-- ============================================================

-- 将独立字段的值合并到 risk_limits 中（如果 risk_limits 中没有对应值）
UPDATE public.bots 
SET risk_limits = COALESCE(risk_limits, '{}'::jsonb) || jsonb_build_object(
    'max_leverage', COALESCE(
        (risk_limits->>'max_leverage')::int, 
        max_leverage, 
        10
    ),
    'max_single_allocation_pct', COALESCE(
        (risk_limits->>'max_single_allocation_pct')::float,
        (risk_limits->>'max_single_symbol_pct')::float * 100,
        max_position_size_percent::float,
        30.0
    )
)
WHERE max_leverage IS NOT NULL 
   OR max_position_size_percent IS NOT NULL;

-- ============================================================
-- Part 2: 删除废弃字段
-- ============================================================

-- 删除 max_leverage 字段
ALTER TABLE public.bots DROP COLUMN IF EXISTS max_leverage;

-- 删除 max_position_size_percent 字段
ALTER TABLE public.bots DROP COLUMN IF EXISTS max_position_size_percent;

-- 删除 max_total_positions 字段
ALTER TABLE public.bots DROP COLUMN IF EXISTS max_total_positions;

-- 删除 max_concurrent_symbols 字段
ALTER TABLE public.bots DROP COLUMN IF EXISTS max_concurrent_symbols;

-- ============================================================
-- Part 3: 验证迁移结果
-- ============================================================

SELECT '✅ Deprecated bot fields removed' AS status;

-- 显示现有 Bot 的 risk_limits 配置
SELECT id, name, 
       risk_limits->>'max_leverage' AS max_leverage,
       risk_limits->>'max_single_allocation_pct' AS max_single_pct,
       risk_limits->>'max_total_allocation_pct' AS max_total_pct
FROM bots 
LIMIT 3;


