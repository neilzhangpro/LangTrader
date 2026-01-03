# tests/test_debate.py
"""
辩论节点单元测试

测试内容：
1. DebateMessage 和 DebateSession 模型
2. 角色配置加载
3. 共识判断逻辑
4. 响应解析
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))

from datetime import datetime

from langtrader_core.graph.state import (
    BatchDecisionResult,
    PortfolioDecision,
    DebateMessage,
    DebateSession,
)


class TestDebateMessage:
    """测试 DebateMessage 模型"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        msg = DebateMessage(
            role="risk_manager",
            round_num=1,
            analysis="仓位合理，风险可控",
            concerns=[],
            proposed_changes=None,
            vote="approve",
        )
        
        assert msg.role == "risk_manager"
        assert msg.round_num == 1
        assert msg.vote == "approve"
        assert len(msg.concerns) == 0
    
    def test_with_concerns(self):
        """测试带关注点的消息"""
        msg = DebateMessage(
            role="contrarian",
            round_num=1,
            analysis="总仓位偏高",
            concerns=["BTC仓位过大", "缺乏多样化"],
            proposed_changes={"BTC/USDC:USDC": {"allocation_pct": 20}},
            vote="modify",
        )
        
        assert msg.vote == "modify"
        assert len(msg.concerns) == 2
        assert msg.proposed_changes is not None
    
    def test_default_values(self):
        """测试默认值"""
        msg = DebateMessage(role="test", round_num=1)
        
        assert msg.analysis == ""
        assert msg.concerns == []
        assert msg.proposed_changes is None
        assert msg.vote == "approve"


class TestDebateSession:
    """测试 DebateSession 模型"""
    
    def test_basic_creation(self):
        """测试基本创建"""
        initial_proposal = BatchDecisionResult(
            decisions=[
                PortfolioDecision(symbol="BTC", action="open_long", allocation_pct=30)
            ],
            total_allocation_pct=30.0,
        )
        
        session = DebateSession(
            initial_proposal=initial_proposal,
            messages=[],
            consensus_reached=False,
            total_rounds=0,
        )
        
        assert session.initial_proposal is not None
        assert len(session.messages) == 0
        assert session.consensus_reached is False
    
    def test_with_messages(self):
        """测试带消息的会话"""
        session = DebateSession(
            initial_proposal=BatchDecisionResult(),
            messages=[
                DebateMessage(role="risk_manager", round_num=1, vote="approve"),
                DebateMessage(role="portfolio_manager", round_num=1, vote="approve"),
                DebateMessage(role="contrarian", round_num=1, vote="modify"),
            ],
            total_rounds=1,
        )
        
        assert len(session.messages) == 3
        assert session.total_rounds == 1


class TestConsensusLogic:
    """测试共识判断逻辑"""
    
    def test_consensus_reached(self):
        """测试达成共识"""
        messages = [
            DebateMessage(role="risk_manager", round_num=1, vote="approve"),
            DebateMessage(role="portfolio_manager", round_num=1, vote="approve"),
            DebateMessage(role="contrarian", round_num=1, vote="approve"),
        ]
        
        threshold = 2
        round_num = 1
        
        round_messages = [m for m in messages if m.round_num == round_num]
        approve_count = sum(1 for m in round_messages if m.vote == "approve")
        
        consensus = approve_count >= threshold
        
        assert consensus is True
        assert approve_count == 3
    
    def test_no_consensus(self):
        """测试未达成共识"""
        messages = [
            DebateMessage(role="risk_manager", round_num=1, vote="reject"),
            DebateMessage(role="portfolio_manager", round_num=1, vote="modify"),
            DebateMessage(role="contrarian", round_num=1, vote="reject"),
        ]
        
        threshold = 2
        round_num = 1
        
        round_messages = [m for m in messages if m.round_num == round_num]
        approve_count = sum(1 for m in round_messages if m.vote == "approve")
        
        consensus = approve_count >= threshold
        
        assert consensus is False
        assert approve_count == 0
    
    def test_partial_consensus(self):
        """测试部分共识"""
        messages = [
            DebateMessage(role="risk_manager", round_num=1, vote="approve"),
            DebateMessage(role="portfolio_manager", round_num=1, vote="approve"),
            DebateMessage(role="contrarian", round_num=1, vote="reject"),
        ]
        
        threshold = 2
        round_num = 1
        
        round_messages = [m for m in messages if m.round_num == round_num]
        approve_count = sum(1 for m in round_messages if m.vote == "approve")
        
        consensus = approve_count >= threshold
        
        assert consensus is True  # 2 >= 2
        assert approve_count == 2


class TestRoleConfig:
    """测试角色配置"""
    
    DEFAULT_ROLES = [
        {
            "id": "risk_manager",
            "name": "风险经理",
            "focus": "检查总仓位、止损设置",
            "style": "保守、谨慎",
            "priority": 1,
        },
        {
            "id": "portfolio_manager",
            "name": "组合经理",
            "focus": "优化仓位分配",
            "style": "平衡、全局视角",
            "priority": 2,
        },
        {
            "id": "contrarian",
            "name": "魔鬼代言人",
            "focus": "挑战假设",
            "style": "批判、追问",
            "priority": 3,
        },
    ]
    
    def test_role_priority_sorting(self):
        """测试角色优先级排序"""
        sorted_roles = sorted(self.DEFAULT_ROLES, key=lambda r: r.get('priority', 99))
        
        assert sorted_roles[0]["id"] == "risk_manager"
        assert sorted_roles[1]["id"] == "portfolio_manager"
        assert sorted_roles[2]["id"] == "contrarian"
    
    def test_role_has_required_fields(self):
        """测试角色必需字段"""
        required_fields = ["id", "name", "focus", "style"]
        
        for role in self.DEFAULT_ROLES:
            for field in required_fields:
                assert field in role, f"Missing field: {field} in role {role.get('id')}"


class TestResponseParsing:
    """测试响应解析"""
    
    def test_parse_json_response(self):
        """测试解析 JSON 响应"""
        import json
        
        content = '''
        {
            "analysis": "提案合理",
            "concerns": [],
            "proposed_changes": null,
            "vote": "approve"
        }
        '''
        
        try:
            parsed = json.loads(content)
            assert parsed["vote"] == "approve"
            assert parsed["concerns"] == []
        except json.JSONDecodeError:
            pytest.fail("JSON parsing failed")
    
    def test_parse_markdown_json_response(self):
        """测试解析 Markdown 代码块中的 JSON"""
        import re
        import json
        
        content = '''
        Some analysis text...
        
        ```json
        {
            "analysis": "需要调整",
            "concerns": ["仓位过高"],
            "proposed_changes": {"BTC": {"allocation_pct": 20}},
            "vote": "modify"
        }
        ```
        '''
        
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        assert json_match is not None
        
        parsed = json.loads(json_match.group(1))
        assert parsed["vote"] == "modify"
        assert len(parsed["concerns"]) == 1
    
    def test_fallback_for_invalid_json(self):
        """测试无效 JSON 的回退处理"""
        content = "This is not valid JSON, just some text analysis."
        
        # 模拟回退逻辑
        try:
            import json
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {
                "analysis": content[:200],
                "concerns": [],
                "proposed_changes": None,
                "vote": "approve",
            }
        
        assert parsed["vote"] == "approve"
        assert "not valid JSON" in parsed["analysis"]


class TestDebateFlow:
    """测试辩论流程"""
    
    def test_early_consensus_exit(self):
        """测试早期共识退出"""
        max_rounds = 3
        
        for round_num in range(1, max_rounds + 1):
            # 模拟每轮的投票
            votes = ["approve", "approve", "approve"]
            approve_count = sum(1 for v in votes if v == "approve")
            
            if approve_count >= 2:  # threshold
                consensus_round = round_num
                break
        else:
            consensus_round = max_rounds
        
        assert consensus_round == 1  # 第一轮就达成共识
    
    def test_max_rounds_reached(self):
        """测试达到最大轮数"""
        max_rounds = 3
        consensus_reached = False
        
        for round_num in range(1, max_rounds + 1):
            # 模拟每轮都有人反对
            votes = ["approve", "reject", "reject"]
            approve_count = sum(1 for v in votes if v == "approve")
            
            if approve_count >= 2:
                consensus_reached = True
                break
        
        assert consensus_reached is False
        assert round_num == max_rounds


if __name__ == "__main__":
    # 运行测试
    test_msg = TestDebateMessage()
    test_msg.test_basic_creation()
    test_msg.test_with_concerns()
    test_msg.test_default_values()
    print("✅ TestDebateMessage passed")
    
    test_session = TestDebateSession()
    test_session.test_basic_creation()
    test_session.test_with_messages()
    print("✅ TestDebateSession passed")
    
    test_consensus = TestConsensusLogic()
    test_consensus.test_consensus_reached()
    test_consensus.test_no_consensus()
    test_consensus.test_partial_consensus()
    print("✅ TestConsensusLogic passed")
    
    test_role = TestRoleConfig()
    test_role.test_role_priority_sorting()
    test_role.test_role_has_required_fields()
    print("✅ TestRoleConfig passed")
    
    test_parse = TestResponseParsing()
    test_parse.test_parse_json_response()
    test_parse.test_parse_markdown_json_response()
    test_parse.test_fallback_for_invalid_json()
    print("✅ TestResponseParsing passed")
    
    test_flow = TestDebateFlow()
    test_flow.test_early_consensus_exit()
    test_flow.test_max_rounds_reached()
    print("✅ TestDebateFlow passed")
    
    print("\n🎉 All debate tests passed!")

