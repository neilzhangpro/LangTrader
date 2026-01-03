-- ============================================================
-- 修复辩论超时配置
-- 
-- 问题：原配置 timeout_per_round = 30 秒对于 Agent 太短
-- 原因：LangChain Agent 需要多轮 LLM 调用（工具选择 → 执行 → 结果处理）
-- 解决：将超时时间从 30 秒增加到 180 秒
-- ============================================================

UPDATE system_configs 
SET config_value = '180', updated_at = NOW()
WHERE config_key = 'debate.timeout_per_round';

SELECT '✅ Updated debate.timeout_per_round to 180s' AS status;

