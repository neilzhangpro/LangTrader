-- ============================================================
-- 更新辩论配置（与代码同步）
-- 
-- 变更：
-- 1. 删除废弃配置：debate.consensus_threshold, debate.timeout_per_round
-- 2. 添加新配置：debate.timeout_per_phase, debate.trade_history_limit
-- 3. 更新角色配置：从 3 个角色更新为 4 个角色（analyst, bull, bear, risk_manager）
-- ============================================================

-- ============================================================
-- Part 1: 删除废弃的配置项
-- ============================================================

DELETE FROM system_configs 
WHERE config_key IN ('debate.consensus_threshold', 'debate.timeout_per_round');

SELECT '✅ 已删除废弃配置: debate.consensus_threshold, debate.timeout_per_round' AS status;

-- ============================================================
-- Part 2: 添加新的配置项
-- ============================================================

INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('debate.timeout_per_phase', '120', 'integer', 'debate', '每阶段超时（秒）', true),
  ('debate.trade_history_limit', '10', 'integer', 'debate', '注入的交易历史条数', true)
ON CONFLICT (config_key) DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  description = EXCLUDED.description,
  updated_at = NOW();

SELECT '✅ 已添加新配置: debate.timeout_per_phase, debate.trade_history_limit' AS status;

-- ============================================================
-- Part 3: 更新角色配置（4 个角色：分析师、多头、空头、风控）
-- ============================================================

UPDATE system_configs 
SET config_value = '[
    {
      "id": "analyst",
      "name": "市场分析师",
      "name_en": "Market Analyst",
      "focus": "技术分析、趋势判断、关键支撑阻力位识别",
      "style": "客观、数据驱动、全面分析",
      "priority": 1
    },
    {
      "id": "bull",
      "name": "多头交易员",
      "name_en": "Bull Trader",
      "focus": "寻找做多机会、识别上涨信号、评估做多胜率",
      "style": "积极、寻找机会、乐观但有依据",
      "priority": 2
    },
    {
      "id": "bear",
      "name": "空头交易员",
      "name_en": "Bear Trader",
      "focus": "寻找做空机会、识别下跌信号、评估做空胜率",
      "style": "谨慎、识别风险、寻找下行机会",
      "priority": 2
    },
    {
      "id": "risk_manager",
      "name": "风险经理",
      "name_en": "Risk Manager",
      "focus": "评估交易风险、验证仓位合理性、确保止损止盈设置正确",
      "style": "平衡、风险意识、促成合理交易",
      "priority": 3
    }
  ]',
  updated_at = NOW()
WHERE config_key = 'debate.roles';

SELECT '✅ 已更新角色配置为 4 个角色' AS status;

-- ============================================================
-- Part 4: 验证迁移结果
-- ============================================================

SELECT '============ 辩论配置更新完成 ============' AS status;

SELECT config_key, config_value, value_type 
FROM system_configs 
WHERE category = 'debate'
ORDER BY config_key;

-- 显示角色数量
SELECT 
  config_key,
  jsonb_array_length(config_value::jsonb) AS role_count
FROM system_configs 
WHERE config_key = 'debate.roles';
