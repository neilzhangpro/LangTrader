-- ============================================================
-- 配置管理系统迁移
-- 
-- 目标：
-- 1. 创建系统配置表 (system_configs)
-- 2. 扩展 bots 表支持动态配置
-- 3. 迁移所有硬编码配置到数据库
-- ============================================================

-- ============================================================
-- Part 1: 创建系统配置表
-- ============================================================

CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value TEXT NOT NULL,
    value_type VARCHAR(50) DEFAULT 'string',
    category VARCHAR(50),
    description TEXT,
    is_editable BOOLEAN DEFAULT true,
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- 添加注释
COMMENT ON TABLE system_configs IS '系统全局配置管理 - 存储所有可配置参数';
COMMENT ON COLUMN system_configs.config_key IS '配置键（唯一，点分隔命名空间）';
COMMENT ON COLUMN system_configs.value_type IS '值类型：string, integer, float, boolean, json';
COMMENT ON COLUMN system_configs.category IS '配置类别：cache, trading, api, system';
COMMENT ON COLUMN system_configs.is_editable IS '是否允许通过 UI 编辑';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_system_configs_category ON system_configs(category);
CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(config_key);

-- ============================================================
-- Part 2: 插入默认配置
-- ============================================================

-- 缓存配置（从 cache.py 迁移）
INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('cache.ttl.tickers', '10', 'integer', 'cache', '行情数据缓存时间(秒)', true),
  ('cache.ttl.ohlcv_3m', '300', 'integer', 'cache', '3分钟K线缓存时间(秒)', true),
  ('cache.ttl.ohlcv_4h', '3600', 'integer', 'cache', '4小时K线缓存时间(秒)', true),
  ('cache.ttl.ohlcv', '600', 'integer', 'cache', '默认K线缓存时间(秒)', true),
  ('cache.ttl.orderbook', '60', 'integer', 'cache', '订单簿缓存时间(秒)', true),
  ('cache.ttl.trades', '60', 'integer', 'cache', '成交记录缓存时间(秒)', true),
  ('cache.ttl.markets', '3600', 'integer', 'cache', '市场信息缓存时间(秒)', true),
  ('cache.ttl.open_interests', '600', 'integer', 'cache', '持仓量缓存时间(秒)', true),
  ('cache.ttl.coin_selection', '600', 'integer', 'cache', '选币缓存时间(秒)', true),
  ('cache.ttl.backtest_ohlcv', '604800', 'integer', 'cache', '回测数据缓存时间(秒)', false)
ON CONFLICT (config_key) DO NOTHING;

-- 交易配置
INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('trading.min_cycle_interval', '60', 'integer', 'trading', '最小交易周期(秒)', true),
  ('trading.max_concurrent_requests', '10', 'integer', 'trading', 'API最大并发数', true),
  ('trading.default_timeframes', '["3m", "4h"]', 'json', 'trading', '默认时间框架', true),
  ('trading.default_ohlcv_limit', '100', 'integer', 'trading', '默认K线数据量', true)
ON CONFLICT (config_key) DO NOTHING;

-- API 限制配置
INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('api.rate_limit.binance', '1200', 'integer', 'api', 'Binance API限制(/分钟)', false),
  ('api.rate_limit.bybit', '120', 'integer', 'api', 'Bybit API限制(/分钟)', false),
  ('api.rate_limit.hyperliquid', '600', 'integer', 'api', 'Hyperliquid API限制(/分钟)', false),
  ('api.default_rate_limit', '60', 'integer', 'api', '未知交易所默认限制(/分钟)', false)
ON CONFLICT (config_key) DO NOTHING;

-- 系统配置
INSERT INTO system_configs (config_key, config_value, value_type, category, description, is_editable) VALUES
  ('system.config_cache_ttl', '60', 'integer', 'system', '配置缓存时间(秒)', true),
  ('system.enable_hot_reload', 'true', 'boolean', 'system', '是否启用配置热重载', true)
ON CONFLICT (config_key) DO NOTHING;

-- ============================================================
-- Part 3: 扩展 bots 表
-- ============================================================

-- 添加动态配置字段
ALTER TABLE bots 
  ADD COLUMN IF NOT EXISTS trading_timeframes JSONB DEFAULT '["3m", "4h"]'::jsonb,
  ADD COLUMN IF NOT EXISTS ohlcv_limits JSONB DEFAULT '{"3m": 100, "4h": 100}'::jsonb,
  ADD COLUMN IF NOT EXISTS indicator_configs JSONB DEFAULT '{
    "ema_periods": [20, 50, 200],
    "rsi_period": 7,
    "macd_config": {"fast": 12, "slow": 26, "signal": 9},
    "atr_period": 14,
    "bollinger_period": 20,
    "bollinger_std": 2.0,
    "stochastic_k": 14,
    "stochastic_d": 3
  }'::jsonb;

-- 添加注释
COMMENT ON COLUMN bots.trading_timeframes IS '交易时间框架列表 (如 ["3m", "4h", "1h"])';
COMMENT ON COLUMN bots.ohlcv_limits IS '各时间框架K线数据获取数量 (如 {"3m": 100, "4h": 100})';
COMMENT ON COLUMN bots.indicator_configs IS '技术指标参数配置 (EMA周期、RSI周期、MACD参数等)';

-- 创建 GIN 索引支持 JSONB 查询
CREATE INDEX IF NOT EXISTS idx_bots_timeframes ON bots USING gin(trading_timeframes);
CREATE INDEX IF NOT EXISTS idx_bots_indicator_configs ON bots USING gin(indicator_configs);

-- ============================================================
-- Part 4: 更新现有 Bot 配置（可选，保持默认值）
-- ============================================================

-- 为现有 Bot 设置默认配置（如果字段为 NULL）
UPDATE bots 
SET 
  trading_timeframes = '["3m", "4h"]'::jsonb,
  ohlcv_limits = '{"3m": 100, "4h": 100}'::jsonb,
  indicator_configs = '{
    "ema_periods": [20, 50, 200],
    "rsi_period": 7,
    "macd_config": {"fast": 12, "slow": 26, "signal": 9},
    "atr_period": 14
  }'::jsonb
WHERE 
  trading_timeframes IS NULL 
  OR ohlcv_limits IS NULL 
  OR indicator_configs IS NULL;

-- ============================================================
-- Part 5: 验证迁移结果
-- ============================================================

-- 检查系统配置表
SELECT '✅ System Configs Table Created' AS status;
SELECT COUNT(*) AS total_configs FROM system_configs;
SELECT category, COUNT(*) AS count 
FROM system_configs 
GROUP BY category 
ORDER BY category;

-- 检查 bots 表新字段
SELECT '✅ Bots Table Extended' AS status;
SELECT 
  id,
  name,
  trading_timeframes,
  ohlcv_limits,
  jsonb_object_keys(indicator_configs) AS indicator_keys
FROM bots
LIMIT 3;

-- 显示配置概览
\echo ''
\echo '============================================================'
\echo '✅ Configuration Management Migration Complete'
\echo '============================================================'
\echo ''
\echo 'Summary:'
\echo '  - system_configs table created with indexes'
\echo '  - Default configurations inserted'
\echo '  - bots table extended with dynamic config fields'
\echo ''
\echo 'Next Steps:'
\echo '  1. Create config_manager.py service'
\echo '  2. Update Cache to load TTL from database'
\echo '  3. Update Market service to use dynamic timeframes'
\echo ''

