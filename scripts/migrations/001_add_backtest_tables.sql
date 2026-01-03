-- 回测任务表
CREATE TABLE IF NOT EXISTS backtest_tasks (
    id SERIAL PRIMARY KEY,
    bot_id INTEGER NOT NULL REFERENCES bots(id),
    name VARCHAR(255) NOT NULL,
    
    -- 时间范围
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    
    -- 回测配置
    initial_balance NUMERIC(20,8) DEFAULT 10000,
    symbols TEXT[],
    
    -- 执行状态
    status VARCHAR(20) DEFAULT 'pending',
    progress NUMERIC(5,2) DEFAULT 0,
    
    -- 结果
    total_cycles INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    final_balance NUMERIC(20,8),
    total_return_usd NUMERIC(20,8),
    return_pct NUMERIC(10,2),
    sharpe_ratio NUMERIC(10,4),
    max_drawdown NUMERIC(10,2),
    
    -- Checkpoint thread_id
    thread_id VARCHAR(255),
    
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_backtest_tasks_bot ON backtest_tasks(bot_id);
CREATE INDEX IF NOT EXISTS idx_backtest_tasks_status ON backtest_tasks(status);

COMMENT ON TABLE backtest_tasks IS '回测任务记录表';

