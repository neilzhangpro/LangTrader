# packages/langtrader_core/services/status_file.py
"""
Bot 状态文件服务

用于在 Bot 进程和 API 之间同步状态信息。
Bot 进程在每个周期结束时写入状态文件，API 读取状态文件获取详细信息。
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from langtrader_core.utils import get_logger

logger = get_logger("status_file")

# 状态文件存放目录（相对于项目根目录）
STATUS_DIR_NAME = "status"


def get_project_root() -> Path:
    """获取项目根目录"""
    # 从当前文件向上查找项目根目录
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # fallback：假设在 packages/langtrader_core/services/ 下
    return Path(__file__).parent.parent.parent.parent


def get_status_dir() -> Path:
    """获取状态文件目录，不存在则创建"""
    status_dir = get_project_root() / STATUS_DIR_NAME
    status_dir.mkdir(parents=True, exist_ok=True)
    return status_dir


def get_status_file_path(bot_id: int) -> Path:
    """获取指定 bot 的状态文件路径"""
    return get_status_dir() / f"bot_{bot_id}.json"


@dataclass
class PositionStatus:
    """持仓状态信息"""
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    entry_price: float
    current_price: float
    pnl_pct: float
    leverage: int = 1
    margin_used: float = 0.0


@dataclass
class BotStatus:
    """Bot 运行状态"""
    bot_id: int
    cycle: int
    balance: float
    initial_balance: float
    positions_count: int
    positions: List[Dict[str, Any]]
    symbols: List[str]
    state: str  # 'running', 'idle', 'error', 'stopped'
    last_decision: Optional[str]  # 最后一次决策摘要
    last_error: Optional[str]
    updated_at: str
    # 辩论决策数据（完整记录辩论过程）
    debate_decision: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotStatus":
        """从字典创建"""
        # 处理可能缺失的 debate_decision 字段
        if 'debate_decision' not in data:
            data['debate_decision'] = None
        return cls(**data)


def write_bot_status(
    bot_id: int,
    cycle: int,
    balance: float,
    initial_balance: float,
    positions: List[Any],
    symbols: List[str],
    state: str = "running",
    last_decision: Optional[str] = None,
    last_error: Optional[str] = None,
    debate_decision: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    写入 Bot 状态到文件
    
    Args:
        bot_id: Bot ID
        cycle: 当前周期数
        balance: 当前余额
        initial_balance: 初始余额
        positions: 当前持仓列表
        symbols: 当前监控的币种列表
        state: 运行状态 ('running', 'idle', 'error', 'stopped')
        last_decision: 最后一次决策摘要
        last_error: 最后一次错误信息
        debate_decision: AI 辩论决策数据（完整记录辩论过程）
    
    Returns:
        是否写入成功
    """
    try:
        # 构建持仓信息
        positions_data = []
        for pos in positions:
            pos_dict = {
                "symbol": getattr(pos, "symbol", str(pos)),
                "side": getattr(pos, "side", "unknown"),
                "amount": float(getattr(pos, "amount", 0)),
                "entry_price": float(getattr(pos, "price", 0)),
                "leverage": int(getattr(pos, "leverage", 1)),
            }
            # 计算保证金（如果有 margin_used 属性）
            if hasattr(pos, "margin_used"):
                pos_dict["margin_used"] = float(pos.margin_used)
            positions_data.append(pos_dict)
        
        # 构建状态对象
        status = BotStatus(
            bot_id=bot_id,
            cycle=cycle,
            balance=balance,
            initial_balance=initial_balance,
            positions_count=len(positions),
            positions=positions_data,
            symbols=symbols,
            state=state,
            last_decision=last_decision,
            last_error=last_error,
            updated_at=datetime.now().isoformat(),
            debate_decision=debate_decision,
        )
        
        # 写入文件
        status_file = get_status_file_path(bot_id)
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status.to_dict(), f, ensure_ascii=False, indent=2)
        
        logger.debug(f"📝 Bot {bot_id} status written to {status_file}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to write bot status: {e}")
        return False


def read_bot_status(bot_id: int) -> Optional[BotStatus]:
    """
    读取 Bot 状态文件
    
    Args:
        bot_id: Bot ID
    
    Returns:
        BotStatus 对象，如果文件不存在或读取失败则返回 None
    """
    try:
        status_file = get_status_file_path(bot_id)
        
        if not status_file.exists():
            logger.debug(f"Status file not found: {status_file}")
            return None
        
        with open(status_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return BotStatus.from_dict(data)
        
    except Exception as e:
        logger.error(f"❌ Failed to read bot status: {e}")
        return None


def read_bot_status_dict(bot_id: int) -> Optional[Dict[str, Any]]:
    """
    读取 Bot 状态文件（返回原始字典）
    
    Args:
        bot_id: Bot ID
    
    Returns:
        状态字典，如果文件不存在或读取失败则返回 None
    """
    try:
        status_file = get_status_file_path(bot_id)
        
        if not status_file.exists():
            return None
        
        with open(status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
        
    except Exception as e:
        logger.error(f"❌ Failed to read bot status: {e}")
        return None


def delete_bot_status(bot_id: int) -> bool:
    """
    删除 Bot 状态文件
    
    Args:
        bot_id: Bot ID
    
    Returns:
        是否删除成功
    """
    try:
        status_file = get_status_file_path(bot_id)
        
        if status_file.exists():
            status_file.unlink()
            logger.info(f"🗑️ Deleted status file: {status_file}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to delete bot status: {e}")
        return False


def mark_bot_stopped(bot_id: int) -> bool:
    """
    标记 Bot 为已停止状态
    
    Args:
        bot_id: Bot ID
    
    Returns:
        是否成功
    """
    try:
        status = read_bot_status(bot_id)
        if status:
            status.state = "stopped"
            status.updated_at = datetime.now().isoformat()
            
            status_file = get_status_file_path(bot_id)
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status.to_dict(), f, ensure_ascii=False, indent=2)
            
            logger.info(f"🛑 Bot {bot_id} marked as stopped")
            return True
        return False
        
    except Exception as e:
        logger.error(f"❌ Failed to mark bot stopped: {e}")
        return False

