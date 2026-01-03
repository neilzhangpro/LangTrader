# packages/langtrader_core/graph/utils.py
"""
图节点公共工具函数

提供节点间共用的工具函数：
- get_free_balance: 从账户获取可用余额
- calculate_position_size: 计算仓位大小
"""
from langtrader_core.graph.state import State
from langtrader_core.utils import get_logger

logger = get_logger("graph_utils")


def get_free_balance(state: State) -> float:
    """获取可用余额（优先 USDC，其次 USDT）"""
    if not state.account:
        return 0.0
    
    free_balance = state.account.free.get('USDC', 0) or state.account.free.get('USDT', 0)
    return float(free_balance) if free_balance else 0.0


def calculate_position_size(
    allocation_pct: float,
    free_balance: float,
    leverage: int = 1
) -> float:
    """
    计算仓位大小
    
    Args:
        allocation_pct: 分配百分比 (0-100)
        free_balance: 可用余额
        leverage: 杠杆倍数
        
    Returns:
        仓位大小（USD）
    """
    base_size = (allocation_pct / 100) * free_balance
    return base_size * leverage


# 导出
__all__ = [
    'get_free_balance',
    'calculate_position_size',
]
