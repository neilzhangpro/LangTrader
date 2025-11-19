-- 1. 币种表现分析表（存储每个币种的历史表现）
CREATE TABLE IF NOT EXISTS coin_performance_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0.00,
    avg_profit_pct DECIMAL(10,4) DEFAULT 0.00,
    avg_loss_pct DECIMAL(10,4) DEFAULT 0.00,
    consecutive_wins INT DEFAULT 0,
    consecutive_losses INT DEFAULT 0,
    total_pnl DECIMAL(15,2) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(trader_id, symbol)
);

-- 2. AI竞争记录表（存储每次多AI竞争的结果）
CREATE TABLE IF NOT EXISTS ai_competitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL,
    competition_time TIMESTAMP DEFAULT NOW(),
    models_competed JSONB NOT NULL,  -- 存储所有模型的决策
    winner_model VARCHAR(50) NOT NULL,
    winner_confidence DECIMAL(5,4) NOT NULL,
    winner_decision JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. AI模型表现统计表
CREATE TABLE IF NOT EXISTS ai_model_performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL,
    model_name VARCHAR(50) NOT NULL,
    total_competitions INT DEFAULT 0,
    times_selected INT DEFAULT 0,
    selection_rate DECIMAL(5,2) DEFAULT 0.00,
    total_trades INT DEFAULT 0,
    winning_trades INT DEFAULT 0,
    losing_trades INT DEFAULT 0,
    win_rate DECIMAL(5,2) DEFAULT 0.00,
    total_pnl DECIMAL(15,2) DEFAULT 0.00,
    avg_confidence DECIMAL(5,4) DEFAULT 0.00,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(trader_id, model_name)
);

-- 4. 修改 decisions 表（添加竞争关联字段）
ALTER TABLE decisions 
ADD COLUMN IF NOT EXISTS competition_id UUID REFERENCES ai_competitions(id),
ADD COLUMN IF NOT EXISTS winner_model VARCHAR(50);

-- 5. 修改 positions 表（添加竞争关联字段）
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS competition_id UUID REFERENCES ai_competitions(id);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_coin_perf_trader ON coin_performance_analysis(trader_id);
CREATE INDEX IF NOT EXISTS idx_competitions_trader ON ai_competitions(trader_id);
CREATE INDEX IF NOT EXISTS idx_model_perf_trader ON ai_model_performance(trader_id);