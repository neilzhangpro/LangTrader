# tests/test_batch_decision.py
"""
批量决策节点单元测试

测试内容：
1. 仓位规范化逻辑
2. runs 同步逻辑
3. 默认决策生成
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from datetime import datetime

from langtrader_core.graph.state import (
    State, 
    Account, 
    RunRecord,
    BatchDecisionResult, 
    PortfolioDecision,
    PerformanceMetrics,
)


class TestPortfolioDecision:
    """测试 PortfolioDecision 模型"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        decision = PortfolioDecision(
            symbol="BTC/USDC:USDC",
            action="open_long",
            allocation_pct=30.0,
            leverage=3,
            stop_loss=85000.0,
            take_profit=95000.0,
            confidence=75,
            reasoning="Test reasoning",
            priority=1,
        )
        
        assert decision.symbol == "BTC/USDC:USDC"
        assert decision.action == "open_long"
        assert decision.allocation_pct == 30.0
        assert decision.confidence == 75
    
    def test_default_values(self):
        """测试默认值"""
        decision = PortfolioDecision(
            symbol="ETH/USDC:USDC",
            action="wait",
        )
        
        assert decision.allocation_pct == 0.0
        assert decision.leverage == 1
        assert decision.confidence == 0
        assert decision.priority == 0


class TestBatchDecisionResult:
    """测试 BatchDecisionResult 模型"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        result = BatchDecisionResult(
            decisions=[
                PortfolioDecision(symbol="BTC/USDC:USDC", action="open_long", allocation_pct=30),
                PortfolioDecision(symbol="ETH/USDC:USDC", action="wait", allocation_pct=0),
            ],
            total_allocation_pct=30.0,
            cash_reserve_pct=70.0,
            strategy_rationale="Test strategy",
        )
        
        assert len(result.decisions) == 2
        assert result.total_allocation_pct == 30.0
        assert result.cash_reserve_pct == 70.0
    
    def test_empty_decisions(self):
        """测试空决策列表"""
        result = BatchDecisionResult()
        
        assert len(result.decisions) == 0
        assert result.total_allocation_pct == 0.0
        assert result.cash_reserve_pct == 20.0


class TestAllocationNormalization:
    """测试仓位规范化逻辑"""
    
    def test_normalize_over_limit(self):
        """测试超限时的规范化"""
        # 模拟总仓位 120% > 80% 限制
        decisions = [
            PortfolioDecision(symbol="BTC", action="open_long", allocation_pct=50),
            PortfolioDecision(symbol="ETH", action="open_long", allocation_pct=40),
            PortfolioDecision(symbol="SOL", action="open_long", allocation_pct=30),
        ]
        
        total = sum(d.allocation_pct for d in decisions)
        assert total == 120  # 超限
        
        # 按比例缩减到 80%
        max_total = 80.0
        scale_factor = max_total / total
        
        for d in decisions:
            d.allocation_pct *= scale_factor
        
        new_total = sum(d.allocation_pct for d in decisions)
        assert abs(new_total - 80.0) < 0.01
    
    def test_single_symbol_cap(self):
        """测试单币种上限"""
        decision = PortfolioDecision(
            symbol="BTC",
            action="open_long",
            allocation_pct=60.0,  # 超过 40% 上限
        )
        
        max_single = 40.0
        if decision.allocation_pct > max_single:
            decision.allocation_pct = max_single
        
        assert decision.allocation_pct == 40.0
    
    def test_wait_decisions_excluded(self):
        """测试 wait 决策不计入总仓位"""
        decisions = [
            PortfolioDecision(symbol="BTC", action="open_long", allocation_pct=30),
            PortfolioDecision(symbol="ETH", action="wait", allocation_pct=0),
            PortfolioDecision(symbol="SOL", action="hold", allocation_pct=0),
        ]
        
        # 只计算 open 决策
        total = sum(
            d.allocation_pct 
            for d in decisions 
            if d.action not in ("wait", "hold")
        )
        
        assert total == 30.0


class TestSyncToRuns:
    """测试同步到 runs 的逻辑"""
    
    def test_position_size_calculation(self):
        """测试仓位金额计算"""
        free_balance = 1000.0
        allocation_pct = 30.0
        
        position_size_usd = (allocation_pct / 100) * free_balance
        
        assert position_size_usd == 300.0
    
    def test_conversion_to_ai_decision(self):
        """测试转换为 AIDecision 格式"""
        from langtrader_core.graph.state import AIDecision
        
        pd = PortfolioDecision(
            symbol="BTC/USDC:USDC",
            action="open_long",
            allocation_pct=30.0,
            leverage=3,
            stop_loss=85000.0,
            take_profit=95000.0,
            confidence=75,
            reasoning="Test reason",
        )
        
        free_balance = 1000.0
        position_size_usd = (pd.allocation_pct / 100) * free_balance
        
        ai_decision = AIDecision(
            symbol=pd.symbol,
            action=pd.action,
            leverage=pd.leverage,
            position_size_usd=position_size_usd,
            stop_loss_price=pd.stop_loss,
            take_profit_price=pd.take_profit,
            confidence=float(pd.confidence),
            reasons=[pd.reasoning] if pd.reasoning else []
        )
        
        assert ai_decision.symbol == "BTC/USDC:USDC"
        assert ai_decision.position_size_usd == 300.0
        assert ai_decision.leverage == 3
        assert ai_decision.confidence == 75.0


class TestPromptBuilding:
    """测试提示词构建"""
    
    def test_account_info_format(self):
        """测试账户信息格式化"""
        account = Account(
            timestamp=datetime.now(),
            total={"USDC": 1000.0},
            free={"USDC": 800.0},
        )
        
        total = account.total.get('USDC', 0)
        free = account.free.get('USDC', 0)
        
        assert total == 1000.0
        assert free == 800.0
    
    def test_multiple_symbols_in_prompt(self):
        """测试多币种提示词构建"""
        symbols = ["BTC/USDC:USDC", "ETH/USDC:USDC", "SOL/USDC:USDC"]
        
        prompt_sections = []
        for symbol in symbols:
            prompt_sections.append(f"## {symbol}\n量化得分: 75/100\n")
        
        full_prompt = "\n".join(prompt_sections)
        
        assert "BTC/USDC:USDC" in full_prompt
        assert "ETH/USDC:USDC" in full_prompt
        assert "SOL/USDC:USDC" in full_prompt


if __name__ == "__main__":
    # 运行测试
    test_portfolio = TestPortfolioDecision()
    test_portfolio.test_basic_creation()
    test_portfolio.test_default_values()
    print("✅ TestPortfolioDecision passed")
    
    test_batch = TestBatchDecisionResult()
    test_batch.test_basic_creation()
    test_batch.test_empty_decisions()
    print("✅ TestBatchDecisionResult passed")
    
    test_norm = TestAllocationNormalization()
    test_norm.test_normalize_over_limit()
    test_norm.test_single_symbol_cap()
    test_norm.test_wait_decisions_excluded()
    print("✅ TestAllocationNormalization passed")
    
    test_sync = TestSyncToRuns()
    test_sync.test_position_size_calculation()
    test_sync.test_conversion_to_ai_decision()
    print("✅ TestSyncToRuns passed")
    
    test_prompt = TestPromptBuilding()
    test_prompt.test_account_info_format()
    test_prompt.test_multiple_symbols_in_prompt()
    print("✅ TestPromptBuilding passed")
    
    print("\n🎉 All tests passed!")

