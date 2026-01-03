-- ============================================================
-- 更新Bot配置为激进交易策略
-- 
-- 用途：提高交易频率，降低开仓门槛
-- 适用：测试和快速迭代场景
-- ============================================================

-- 备份当前配置（可选）
-- CREATE TABLE IF NOT EXISTS bots_config_backup AS 
-- SELECT * FROM bots WHERE id = 1;

-- 更新Bot 1为激进策略
UPDATE bots SET 
  -- 1. 使用激进提示词
  prompt = 'aggressive.txt',
  
  -- 2. 降低量化过滤阈值（更多币种通过）
  quant_signal_threshold = 40,
  
  -- 3. 调整量化权重（提高动量和量能权重）
  quant_signal_weights = '{
    "trend": 0.3,
    "momentum": 0.4,
    "volume": 0.2,
    "sentiment": 0.1
  }'::jsonb,
  
  -- 4. 放宽风险限制
  risk_limits = '{
    "max_total_exposure_pct": 1.5,
    "max_consecutive_losses": 20,
    "max_single_symbol_pct": 0.6
  }'::jsonb,
  
  -- 5. 提高杠杆和仓位上限
  max_leverage = 5,
  max_position_size_percent = 60.00,
  
  -- 6. 更新时间戳
  updated_at = NOW()
  
WHERE id = 1;

-- 验证更新结果
SELECT 
  id,
  name,
  prompt,
  quant_signal_threshold,
  quant_signal_weights,
  max_leverage,
  max_position_size_percent,
  risk_limits
FROM bots 
WHERE id = 1;

-- 输出确认信息
\echo '✅ Bot configuration updated to aggressive strategy'
\echo ''
\echo 'Key changes:'
\echo '  - Prompt: aggressive.txt'
\echo '  - Quant threshold: 40 (was 50)'
\echo '  - Max leverage: 5'
\echo '  - Max position size: 60%'
\echo '  - Risk limits: relaxed'
\echo ''
\echo 'Run backtest to test: uv run examples/run_backtest.py'

