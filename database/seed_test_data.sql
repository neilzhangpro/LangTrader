-- ============================================
-- 测试数据插入
-- 2个 traders，每个20条 positions
-- ============================================

INSERT INTO traders (id, name, exchange, symbols, llm_config, exchange_configs, risk_config, system_prompt, status)
VALUES 
-- Trader 1: 保守型（胜率高）
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 
 'Conservative Trader', 
 'hyperliquid',
 '["BTC", "ETH"]'::jsonb,
 '{"openai": {"model": "gpt-4", "api_key": "sk-test-conservative", "base_url": "https://api.openai.com/v1"}}'::jsonb,
 '{"account_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", "secret_key": "0xaaaa"}'::jsonb,
 '{"max_position_size": 0.1, "max_leverage": 2, "stop_loss_percent": 0.02, "take_profit_percent": 0.05}'::jsonb,
 'You are a conservative trader focusing on capital preservation with steady gains.',
 'active'),

-- Trader 2: 激进型（胜率低但盈亏比高）
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
 'Aggressive Trader',
 'hyperliquid',
 '["BTC", "ETH", "SOL"]'::jsonb,
 '{"openai": {"model": "gpt-4", "api_key": "sk-test-aggressive", "base_url": "https://api.openai.com/v1"}}'::jsonb,
 '{"account_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "secret_key": "0xbbbb"}'::jsonb,
 '{"max_position_size": 0.25, "max_leverage": 5, "stop_loss_percent": 0.05, "take_profit_percent": 0.12}'::jsonb,
 'You are an aggressive trader seeking high returns with calculated risks.',
 'active');

-- ============================================
-- Trader 1 的 20 条记录（14盈6亏，胜率70%）
-- ============================================
INSERT INTO positions (trader_id, symbol, side, entry_price, exit_price, quantity, leverage, stop_loss, take_profit, exit_reason, status, opened_at, closed_at)
VALUES
-- 盈利交易（14笔）
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 98000, 99900, 0.005, 2, 97000, 100000, 'take_profit', 'closed', NOW() - INTERVAL '20 days', NOW() - INTERVAL '19.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3200, 3296, 0.5, 2, 3100, 3300, 'take_profit', 'closed', NOW() - INTERVAL '19 days', NOW() - INTERVAL '18.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 99500, 101490, 0.004, 2, 98500, 102000, 'take_profit', 'closed', NOW() - INTERVAL '18 days', NOW() - INTERVAL '17.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3250, 3347.5, 0.4, 2, 3150, 3400, 'take_profit', 'closed', NOW() - INTERVAL '17 days', NOW() - INTERVAL '16.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 100000, 101900, 0.003, 2, 99000, 102500, 'take_profit', 'closed', NOW() - INTERVAL '16 days', NOW() - INTERVAL '15.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3300, 3363, 0.3, 2, 3200, 3450, 'take_profit', 'closed', NOW() - INTERVAL '15 days', NOW() - INTERVAL '14.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 101000, 102979, 0.0025, 2, 100000, 103500, 'take_profit', 'closed', NOW() - INTERVAL '14 days', NOW() - INTERVAL '13.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3350, 3450.5, 0.35, 2, 3250, 3500, 'take_profit', 'closed', NOW() - INTERVAL '13 days', NOW() - INTERVAL '12.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 99800, 101694, 0.0045, 2, 98800, 102000, 'take_profit', 'closed', NOW() - INTERVAL '12 days', NOW() - INTERVAL '11.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3280, 3362.4, 0.38, 2, 3180, 3420, 'take_profit', 'closed', NOW() - INTERVAL '11 days', NOW() - INTERVAL '10.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 100500, 102510, 0.003, 2, 99500, 103000, 'take_profit', 'closed', NOW() - INTERVAL '10 days', NOW() - INTERVAL '9.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3320, 3386.4, 0.32, 2, 3220, 3470, 'take_profit', 'closed', NOW() - INTERVAL '9 days', NOW() - INTERVAL '8.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 101200, 103122, 0.0028, 2, 100200, 103700, 'take_profit', 'closed', NOW() - INTERVAL '8 days', NOW() - INTERVAL '7.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3370, 3438.7, 0.29, 2, 3270, 3520, 'take_profit', 'closed', NOW() - INTERVAL '7 days', NOW() - INTERVAL '6.5 days'),

-- 亏损交易（6笔）
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 102000, 100960, 0.003, 2, 101000, 104500, 'stop_loss', 'closed', NOW() - INTERVAL '6 days', NOW() - INTERVAL '5.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3400, 3332, 0.28, 2, 3300, 3550, 'stop_loss', 'closed', NOW() - INTERVAL '5 days', NOW() - INTERVAL '4.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 103000, 101940, 0.0027, 2, 102000, 105500, 'stop_loss', 'closed', NOW() - INTERVAL '4 days', NOW() - INTERVAL '3.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3450, 3381, 0.26, 2, 3350, 3600, 'stop_loss', 'closed', NOW() - INTERVAL '3 days', NOW() - INTERVAL '2.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'BTC', 'LONG', 102500, 101475, 0.0029, 2, 101500, 105000, 'stop_loss', 'closed', NOW() - INTERVAL '2 days', NOW() - INTERVAL '1.5 days'),
('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'ETH', 'LONG', 3420, 3352.8, 0.27, 2, 3320, 3570, 'stop_loss', 'closed', NOW() - INTERVAL '1 days', NOW() - INTERVAL '12 hours');

-- ============================================
-- Trader 2 的 20 条记录（8盈12亏，胜率40%但盈亏比高）
-- ============================================
INSERT INTO positions (trader_id, symbol, side, entry_price, exit_price, quantity, leverage, stop_loss, take_profit, exit_reason, status, opened_at, closed_at)
VALUES
-- 盈利交易（8笔，单笔大）
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 95000, 104500, 0.01, 5, 93000, 106000, 'take_profit', 'closed', NOW() - INTERVAL '20 days', NOW() - INTERVAL '19.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3100, 3472, 0.8, 5, 2950, 3500, 'take_profit', 'closed', NOW() - INTERVAL '19 days', NOW() - INTERVAL '18.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'LONG', 170, 190.4, 6.0, 5, 162, 195, 'take_profit', 'closed', NOW() - INTERVAL '18 days', NOW() - INTERVAL '17.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'SHORT', 103000, 92700, 0.009, 5, 105000, 91000, 'take_profit', 'closed', NOW() - INTERVAL '17 days', NOW() - INTERVAL '16.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3200, 3584, 0.75, 5, 3040, 3600, 'take_profit', 'closed', NOW() - INTERVAL '16 days', NOW() - INTERVAL '15.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'SHORT', 188, 167.72, 5.5, 5, 195, 165, 'take_profit', 'closed', NOW() - INTERVAL '15 days', NOW() - INTERVAL '14.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 97000, 106700, 0.0085, 5, 95000, 108000, 'take_profit', 'closed', NOW() - INTERVAL '14 days', NOW() - INTERVAL '13.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3250, 3640, 0.7, 5, 3090, 3700, 'take_profit', 'closed', NOW() - INTERVAL '13 days', NOW() - INTERVAL '12.5 days'),

-- 亏损交易（12笔，单笔小）
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 100000, 95000, 0.0075, 5, 99000, 105000, 'stop_loss', 'closed', NOW() - INTERVAL '12 days', NOW() - INTERVAL '11.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'LONG', 182, 172.9, 5.2, 5, 177, 195, 'stop_loss', 'closed', NOW() - INTERVAL '11 days', NOW() - INTERVAL '10.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3330, 3163.5, 0.68, 5, 3230, 3490, 'stop_loss', 'closed', NOW() - INTERVAL '10 days', NOW() - INTERVAL '9.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 101500, 96425, 0.007, 5, 100500, 106500, 'stop_loss', 'closed', NOW() - INTERVAL '9 days', NOW() - INTERVAL '8.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'SHORT', 179, 188.95, 5.0, 5, 184, 170, 'stop_loss', 'closed', NOW() - INTERVAL '8 days', NOW() - INTERVAL '7.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3360, 3192, 0.66, 5, 3260, 3530, 'stop_loss', 'closed', NOW() - INTERVAL '7 days', NOW() - INTERVAL '6.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 102000, 96900, 0.0072, 5, 101000, 107000, 'stop_loss', 'closed', NOW() - INTERVAL '6 days', NOW() - INTERVAL '5.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'LONG', 185, 175.75, 4.9, 5, 180, 198, 'stop_loss', 'closed', NOW() - INTERVAL '5 days', NOW() - INTERVAL '4.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3380, 3211.5, 0.65, 5, 3280, 3550, 'stop_loss', 'closed', NOW() - INTERVAL '4 days', NOW() - INTERVAL '3.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'BTC', 'LONG', 103500, 98325, 0.0069, 5, 102500, 108500, 'stop_loss', 'closed', NOW() - INTERVAL '3 days', NOW() - INTERVAL '2.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'SOL', 'LONG', 186, 176.7, 4.8, 5, 181, 199, 'stop_loss', 'closed', NOW() - INTERVAL '2 days', NOW() - INTERVAL '1.5 days'),
('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'ETH', 'LONG', 3390, 3220.5, 0.64, 5, 3290, 3560, 'stop_loss', 'closed', NOW() - INTERVAL '1 days', NOW() - INTERVAL '12 hours');

-- 验证插入
DO $$
DECLARE
    trader1_stats RECORD;
    trader2_stats RECORD;
BEGIN
    -- Trader 1 统计
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE realized_pnl > 0) as wins,
        ROUND(SUM(realized_pnl)::NUMERIC, 2) as total_pnl,
        ROUND((COUNT(*) FILTER (WHERE realized_pnl > 0)::NUMERIC / COUNT(*)::NUMERIC * 100), 1) as win_rate
    INTO trader1_stats
    FROM positions 
    WHERE trader_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
    
    -- Trader 2 统计
    SELECT 
        COUNT(*) as total,
        COUNT(*) FILTER (WHERE realized_pnl > 0) as wins,
        ROUND(SUM(realized_pnl)::NUMERIC, 2) as total_pnl,
        ROUND((COUNT(*) FILTER (WHERE realized_pnl > 0)::NUMERIC / COUNT(*)::NUMERIC * 100), 1) as win_rate
    INTO trader2_stats
    FROM positions 
    WHERE trader_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
    
    RAISE NOTICE '✅ 测试数据插入成功';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Conservative Trader:';
    RAISE NOTICE '  交易数: %, 盈利: %笔, 胜率: %%, 总盈亏: $%', 
        trader1_stats.total, trader1_stats.wins, trader1_stats.win_rate, trader1_stats.total_pnl;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 Aggressive Trader:';
    RAISE NOTICE '  交易数: %, 盈利: %笔, 胜率: %%, 总盈亏: $%',
        trader2_stats.total, trader2_stats.wins, trader2_stats.win_rate, trader2_stats.total_pnl;
END $$;
