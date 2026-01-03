-- 量化信号权重配置 (JSON格式)
ALTER TABLE public.bots ADD COLUMN IF NOT EXISTS quant_signal_weights JSONB DEFAULT '{
    "trend": 0.4,
    "momentum": 0.3,
    "volume": 0.2,
    "sentiment": 0.1
}'::jsonb;

COMMENT ON COLUMN public.bots.quant_signal_weights IS '量化信号权重配置 (趋势/动量/量能/情绪)';

-- 量化信号过滤阈值
ALTER TABLE public.bots ADD COLUMN IF NOT EXISTS quant_signal_threshold INTEGER DEFAULT 50;
COMMENT ON COLUMN public.bots.quant_signal_threshold IS '量化信号最低得分阈值 (0-100)';

-- 动态风险管理配置 (JSON格式)
ALTER TABLE public.bots ADD COLUMN IF NOT EXISTS risk_limits JSONB DEFAULT '{
    "max_total_exposure_pct": 0.8,
    "max_consecutive_losses": 5,
    "max_single_symbol_pct": 0.3
}'::jsonb;

COMMENT ON COLUMN public.bots.risk_limits IS '动态风险管理阈值配置';

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_bots_quant_config ON public.bots USING GIN (quant_signal_weights);
CREATE INDEX IF NOT EXISTS idx_bots_risk_config ON public.bots USING GIN (risk_limits);

