-- 权益历史表（记录每次决策后的账户状态）
CREATE TABLE equity_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trader_id UUID NOT NULL REFERENCES traders(id),
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    -- 账户数据
    equity DECIMAL(18,8) NOT NULL,           -- 账户净值
    withdrawable DECIMAL(18,8),              -- 可用余额
    margin_used DECIMAL(18,8),               -- 已用保证金
    -- 持仓数据
    open_positions INT DEFAULT 0,            -- 持仓数量
    total_position_value DECIMAL(18,8),      -- 总仓位价值
    -- 盈亏数据
    unrealized_pnl DECIMAL(18,8),            -- 浮动盈亏
    realized_pnl_total DECIMAL(18,8),        -- 累计已实现盈亏
    -- 关联决策
    decision_id UUID REFERENCES decisions(id),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_equity_trader_time ON equity_history(trader_id, timestamp DESC);

-- 实时性能缓存表（避免每次都计算）
CREATE TABLE performance_cache (
    trader_id UUID PRIMARY KEY REFERENCES traders(id),
    -- 基础指标
    total_trades INT,
    win_rate DECIMAL(5,4),
    total_pnl DECIMAL(18,8),
    -- 风险指标
    sharpe_ratio DECIMAL(10,4),              -- 夏普率
    max_drawdown DECIMAL(10,4),              -- 最大回撤
    current_drawdown DECIMAL(10,4),          -- 当前回撤
    -- 状态判断
    performance_status VARCHAR(20),          -- 'excellent', 'good', 'poor', '危险'
    risk_level VARCHAR(20),                  -- 'low', 'medium', 'high'
    -- 更新时间
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(trader_id)
);