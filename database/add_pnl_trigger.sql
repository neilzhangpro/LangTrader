-- ============================================
-- 添加自动计算 PnL 的触发器
-- ============================================

CREATE OR REPLACE FUNCTION auto_calculate_position_pnl()
RETURNS TRIGGER AS $$
BEGIN
    -- 当有 exit_price 时自动计算 PnL
    IF NEW.exit_price IS NOT NULL THEN
        NEW.realized_pnl = calc_pnl(
            NEW.side,
            NEW.entry_price,
            NEW.exit_price,
            NEW.quantity,
            NEW.leverage
        );
        
        -- 自动设置 closed_at
        IF NEW.status = 'closed' AND NEW.closed_at IS NULL THEN
            NEW.closed_at = NOW();
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 删除旧触发器（如果存在）
DROP TRIGGER IF EXISTS trg_auto_calculate_pnl ON positions;

-- 创建新触发器
CREATE TRIGGER trg_auto_calculate_pnl
    BEFORE INSERT OR UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION auto_calculate_position_pnl();

SELECT '✅ PnL 自动计算触发器创建成功' AS status;

