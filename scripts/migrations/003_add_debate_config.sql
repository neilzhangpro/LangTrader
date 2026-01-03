-- ============================================================
-- 辩论配置 & 批量决策配置 迁移
-- 
-- 目标：
-- 1. 将 debate_roles.yaml 中的配置迁移到 system_configs 表
-- 2. 添加 batch_decision 节点配置到 system_configs 表
-- ============================================================

-- ============================================================
-- Part 1: 添加辩论全局配置
-- ============================================================

INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('debate.enabled', 'true', 'boolean', 'debate', '是否启用辩论机制', true),
  ('debate.max_rounds', '3', 'integer', 'debate', '最大辩论轮数', true),
  ('debate.consensus_threshold', '2', 'integer', 'debate', '达成共识所需的 approve 票数', true),
  ('debate.timeout_per_round', '180', 'integer', 'debate', '每轮辩论超时（秒）', true)
ON CONFLICT (config_key) DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  updated_at = NOW();

-- ============================================================
-- Part 1.5: 添加批量决策配置
-- ============================================================

INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('batch_decision.max_total_allocation_pct', '80.0', 'float', 'batch_decision', '最大总仓位百分比', true),
  ('batch_decision.max_single_allocation_pct', '40.0', 'float', 'batch_decision', '单币种最大仓位百分比', true),
  ('batch_decision.min_cash_reserve_pct', '20.0', 'float', 'batch_decision', '最小现金储备百分比', true),
  ('batch_decision.timeout_seconds', '90', 'integer', 'batch_decision', 'LLM 调用超时（秒）', true)
ON CONFLICT (config_key) DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  updated_at = NOW();

-- ============================================================
-- Part 2: 添加辩论角色配置（JSON 格式）
-- ============================================================

INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('debate.roles', '[
    {
      "id": "risk_manager",
      "name": "风险经理",
      "name_en": "Risk Manager",
      "focus": "检查总仓位是否过高（应 <= 80%）；验证单币种仓位是否合理（应 <= 40%）；评估止损设置是否合理；识别高度相关的仓位（避免集中风险）；检查风险回报比（应 >= 2:1）",
      "style": "保守、谨慎、注重资本保护",
      "priority": 1
    },
    {
      "id": "portfolio_manager",
      "name": "组合经理",
      "name_en": "Portfolio Manager",
      "focus": "优化仓位分配比例；确保多样化，避免过度集中；评估币种之间的相关性；平衡风险与收益；考虑整体投资组合的夏普比率",
      "style": "平衡、全局视角、追求最优配比",
      "priority": 2
    },
    {
      "id": "contrarian",
      "name": "魔鬼代言人",
      "name_en": "Devil''s Advocate",
      "focus": "挑战所有假设；找出决策中的漏洞；质疑过高的信心度；提出最坏情况场景；反驳过于乐观的判断",
      "style": "批判、追问、不轻易认同",
      "priority": 3
    }
  ]', 'json', 'debate', '辩论角色列表（JSON 数组）', true)
ON CONFLICT (config_key) DO UPDATE SET 
  config_value = EXCLUDED.config_value,
  updated_at = NOW();

-- ============================================================
-- Part 3: 验证迁移结果
-- ============================================================

SELECT '✅ Debate & BatchDecision Configuration Migration Complete' AS status;

SELECT config_key, value_type, category 
FROM system_configs 
WHERE category IN ('debate', 'batch_decision')
ORDER BY category, config_key;

-- 显示角色数量
SELECT 
  config_key,
  jsonb_array_length(config_value::jsonb) AS role_count
FROM system_configs 
WHERE config_key = 'debate.roles';

