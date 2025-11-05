-- ============================================
-- AI Trading System - Minimal Schema
-- ============================================
-- Core tables only, no redundancy
-- ============================================
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================
-- 1. TRADERS (Core configuration)
-- ============================================
CREATE TABLE traders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    exchange VARCHAR(50) NOT NULL,
    symbols JSONB NOT NULL,
    -- LLM config
    llm_config JSONB NOT NULL,
    -- Risk config
    risk_config JSONB NOT NULL,
    -- System prompt (updated by learning)
    system_prompt TEXT NOT NULL,
    
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_traders_status ON traders(status);

-- ============================================
-- 2. DECISIONS (Every analysis & decision)
-- ============================================
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id) ON DELETE CASCADE,
    symbol VARCHAR(20) NOT NULL,
    -- Market snapshot
    market_data JSONB NOT NULL,
    -- Technical indicators
    indicators JSONB NOT NULL,
    -- LLM analysis result
    llm_analysis JSONB NOT NULL,
    -- Final decision
    action VARCHAR(10) NOT NULL,  -- BUY/SELL/HOLD
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    -- Risk check result
    risk_passed BOOLEAN NOT NULL DEFAULT FALSE,
    rejection_reason TEXT,
    -- Execution status
    executed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_decisions_trader_time ON decisions(trader_id, created_at DESC);
CREATE INDEX idx_decisions_executed ON decisions(executed);

-- ============================================
-- 3. POSITIONS (Open & closed positions)
-- ============================================
CREATE TABLE positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id) ON DELETE CASCADE,
    decision_id UUID REFERENCES decisions(id),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,  -- LONG/SHORT
    -- Entry
    entry_price DECIMAL(18, 8) NOT NULL,
    quantity DECIMAL(18, 8) NOT NULL,
    leverage INT NOT NULL DEFAULT 1,
    -- Exit
    exit_price DECIMAL(18, 8),
    exit_reason VARCHAR(50),
    -- Risk params
    stop_loss DECIMAL(18, 8),
    take_profit DECIMAL(18, 8),
    -- PnL
    realized_pnl DECIMAL(18, 8),
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    opened_at TIMESTAMP NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMP
);

CREATE INDEX idx_positions_trader_status ON positions(trader_id, status);
CREATE INDEX idx_positions_opened_at ON positions(opened_at DESC);

-- ============================================
-- 4. LEARNING_LOGS (Self-improvement records)
-- ============================================
CREATE TABLE learning_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id) ON DELETE CASCADE,
    -- Input: recent performance data
    input_summary JSONB NOT NULL,
    -- Output: LLM insights
    insights TEXT NOT NULL,
    -- Strategy changes
    strategy_updates JSONB,
    -- Prompt evolution
    old_prompt TEXT,
    new_prompt TEXT,
    applied BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_learning_logs_trader_time ON learning_logs(trader_id, created_at DESC);

-- ============================================
-- VIEWS
-- ============================================

-- Trader performance summary
CREATE VIEW v_trader_stats AS
SELECT 
    t.id,
    t.name,
    t.status,
    COUNT(DISTINCT d.id) as total_decisions,
    COUNT(DISTINCT CASE WHEN d.executed THEN d.id END) as executed_count,
    COUNT(DISTINCT p.id) as total_trades,
    COUNT(DISTINCT CASE WHEN p.status = 'open' THEN p.id END) as open_positions,
    COUNT(DISTINCT CASE WHEN p.realized_pnl > 0 THEN p.id END) as winning_trades,
    COUNT(DISTINCT CASE WHEN p.realized_pnl < 0 THEN p.id END) as losing_trades,
    COALESCE(SUM(p.realized_pnl), 0) as total_pnl,
    CASE 
        WHEN COUNT(DISTINCT CASE WHEN p.status = 'closed' THEN p.id END) > 0 
        THEN ROUND(
            COUNT(DISTINCT CASE WHEN p.realized_pnl > 0 THEN p.id END)::NUMERIC / 
            COUNT(DISTINCT CASE WHEN p.status = 'closed' THEN p.id END)::NUMERIC, 
            4
        )
        ELSE 0 
    END as win_rate
FROM traders t
LEFT JOIN decisions d ON t.id = d.trader_id
LEFT JOIN positions p ON t.id = p.trader_id
GROUP BY t.id, t.name, t.status;

-- ============================================
-- FUNCTIONS
-- ============================================

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_traders_updated_at
    BEFORE UPDATE ON traders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Calculate position PnL
CREATE OR REPLACE FUNCTION calc_pnl(
    p_side VARCHAR,
    p_entry_price DECIMAL,
    p_exit_price DECIMAL,
    p_quantity DECIMAL,
    p_leverage INT
)
RETURNS DECIMAL AS $$
BEGIN
    IF p_side = 'LONG' THEN
        RETURN (p_exit_price - p_entry_price) * p_quantity * p_leverage;
    ELSE
        RETURN (p_entry_price - p_exit_price) * p_quantity * p_leverage;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- SEED DATA
-- ============================================

INSERT INTO traders (name, exchange, symbols, llm_config, risk_config, system_prompt)
VALUES (
    'Demo Trader',
    'mock',
    '["BTCUSDT"]'::jsonb,
    '{"provider":"openai","model":"gpt-4","temperature":0.7}'::jsonb,
    '{"max_position_size":0.1,"max_leverage":3,"stop_loss_percent":0.03,"take_profit_percent":0.06}'::jsonb,
    'You are a professional cryptocurrency trader. Analyze market data and make rational decisions based on technical indicators.'
);

-- ============================================
-- COMPLETION
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '✅ Minimal schema created successfully!';
    RAISE NOTICE '📊 Tables: 4 (traders, decisions, positions, learning_logs)';
    RAISE NOTICE '👁️  Views: 1 (v_trader_stats)';
    RAISE NOTICE '⚡ Functions: 2 (update_updated_at, calc_pnl)';
END;
$$;
