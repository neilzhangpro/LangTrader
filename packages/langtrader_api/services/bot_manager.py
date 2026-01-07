"""
Bot Process Manager
Manages trading bot lifecycle using subprocesses

状态同步机制：
- Bot 进程每个周期结束时写入状态文件 (status/bot_{id}.json)
- API 通过读取状态文件获取详细运行信息（周期数、余额、持仓等）
"""
import subprocess
import asyncio
import signal
import os
import json
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

from langtrader_api.config import settings


@dataclass
class ProcessInfo:
    """Information about a running bot process"""
    bot_id: int
    process: subprocess.Popen
    started_at: datetime
    cycle: int = 0
    error: Optional[str] = None
    log_handle: Optional[Any] = None  # 日志文件句柄，用于重定向 stdout/stderr
    

class BotManager:
    """
    Manages bot processes
    
    Provides start/stop/status operations for trading bots.
    Each bot runs as a separate subprocess.
    """
    
    def __init__(self):
        self._processes: Dict[int, ProcessInfo] = {}
        # 计算项目根目录路径：
        # __file__ = .../packages/langtrader_api/services/bot_manager.py
        # .parent (1) = .../packages/langtrader_api/services/
        # .parent (2) = .../packages/langtrader_api/
        # .parent (3) = .../packages/
        # .parent (4) = .../  (项目根目录)
        self._project_root = Path(__file__).parent.parent.parent.parent
    
    def start_bot(self, bot_id: int, dry_run: bool = False) -> bool:
        """
        Start a trading bot as a subprocess
        
        Args:
            bot_id: The bot ID to start
            dry_run: If True, don't execute actual trades
            
        Returns:
            True if started successfully
            
        Note:
            Bot 日志会被重定向到 logs/bot_{id}.log 文件，
            避免使用 subprocess.PIPE 导致缓冲区满时进程阻塞。
        """
        if bot_id in self._processes:
            raise ValueError(f"Bot {bot_id} is already running")
        
        # Build command
        script_path = self._project_root / settings.BOT_SCRIPT_PATH
        
        if not script_path.exists():
            raise FileNotFoundError(f"Bot script not found: {script_path}")
        
        # 在 Docker 容器中使用 python 直接运行（venv 已激活在 PATH 中）
        # 在本地开发时也可以使用 python 运行
        cmd = ["python", str(script_path)]
        
        # Add bot_id argument (modify run_once.py to accept this)
        # For now, we'll set it as environment variable
        env = os.environ.copy()
        env["BOT_ID"] = str(bot_id)
        
        if dry_run:
            env["DRY_RUN"] = "1"
        
        # 创建日志目录和文件
        # 重定向 stdout/stderr 到日志文件，避免 PIPE 缓冲区满导致进程阻塞
        log_dir = self._project_root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"bot_{bot_id}.log"
        
        # 打开日志文件（追加模式），保存句柄以便后续关闭
        log_handle = open(log_file, 'a', encoding='utf-8', buffering=1)  # 行缓冲
        
        # Start process
        process = subprocess.Popen(
            cmd,
            cwd=str(self._project_root),
            env=env,
            stdout=log_handle,
            stderr=subprocess.STDOUT,  # stderr 也写入 stdout（同一个日志文件）
            # Don't create new process group on Windows
            start_new_session=True if os.name != 'nt' else False,
        )
        
        self._processes[bot_id] = ProcessInfo(
            bot_id=bot_id,
            process=process,
            started_at=datetime.now(),
            log_handle=log_handle,
        )
        
        return True
    
    def stop_bot(self, bot_id: int, force: bool = False) -> bool:
        """
        Stop a running bot
        
        Args:
            bot_id: The bot ID to stop
            force: If True, use SIGKILL instead of SIGTERM
            
        Returns:
            True if stopped successfully
        """
        if bot_id not in self._processes:
            return False
        
        info = self._processes[bot_id]
        process = info.process
        
        if process.poll() is not None:
            # Process already finished, close log handle and cleanup
            self._close_log_handle(info)
            del self._processes[bot_id]
            return True
        
        try:
            if force:
                process.kill()
            else:
                # Send SIGTERM for graceful shutdown
                if os.name == 'nt':
                    process.terminate()
                else:
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            
            # Wait for process to finish (with timeout)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                # Force kill if didn't stop gracefully
                process.kill()
                process.wait()
            
            # 关闭日志文件句柄
            self._close_log_handle(info)
            
            # 更新状态文件，标记为已停止
            from langtrader_core.services.status_file import mark_bot_stopped
            mark_bot_stopped(bot_id)
            
            del self._processes[bot_id]
            return True
            
        except Exception as e:
            self._processes[bot_id].error = str(e)
            return False
    
    def _close_log_handle(self, info: ProcessInfo):
        """
        关闭进程的日志文件句柄
        
        Args:
            info: ProcessInfo 对象
        """
        if info.log_handle:
            try:
                info.log_handle.close()
            except Exception:
                pass
    
    async def stop_all(self):
        """Stop all running bots (called on shutdown)"""
        bot_ids = list(self._processes.keys())
        for bot_id in bot_ids:
            try:
                self.stop_bot(bot_id)
            except Exception:
                pass
    
    def is_running(self, bot_id: int) -> bool:
        """Check if a bot is currently running"""
        if bot_id not in self._processes:
            return False
        
        info = self._processes[bot_id]
        process = info.process
        
        # Check if process is still alive
        if process.poll() is not None:
            # Process has finished, close log handle and cleanup
            self._close_log_handle(info)
            del self._processes[bot_id]
            return False
        
        return True
    
    def get_process_info(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """Get information about a running bot"""
        if bot_id not in self._processes:
            return None
        
        info = self._processes[bot_id]
        process = info.process
        
        # Calculate uptime
        uptime = int((datetime.now() - info.started_at).total_seconds())
        
        # Check if still running
        is_alive = process.poll() is None
        
        return {
            "bot_id": bot_id,
            "pid": process.pid,
            "started_at": info.started_at.isoformat(),
            "uptime": uptime,
            "is_alive": is_alive,
            "cycle": info.cycle,
            "error": info.error,
            "return_code": process.returncode if not is_alive else None,
        }
    
    def list_running(self) -> Dict[int, Dict[str, Any]]:
        """List all running bots"""
        result = {}
        
        # Clean up finished processes
        finished = []
        for bot_id in self._processes:
            if not self.is_running(bot_id):
                finished.append(bot_id)
        
        for bot_id in finished:
            if bot_id in self._processes:
                del self._processes[bot_id]
        
        # Get info for running bots
        for bot_id in self._processes:
            info = self.get_process_info(bot_id)
            if info:
                result[bot_id] = info
        
        return result
    
    def get_logs(self, bot_id: int, lines: int = 100) -> Optional[str]:
        """
        Get recent logs for a bot
        
        首先尝试读取 bot 专属日志文件 (logs/bot_{id}.log)，
        如果不存在则回退到全局日志文件 (logs/langtrader.log)。
        """
        # 优先读取 bot 专属日志文件
        bot_log_file = self._project_root / "logs" / f"bot_{bot_id}.log"
        
        if bot_log_file.exists():
            try:
                with open(bot_log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
                    return "".join(all_lines[-lines:])
            except Exception:
                pass
        
        # 回退：从全局日志文件读取
        global_log_file = self._project_root / "logs" / "langtrader.log"
        
        if not global_log_file.exists():
            return None
        
        try:
            with open(global_log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                # Filter lines for this bot (if logged with bot_id)
                bot_lines = [l for l in all_lines if f"bot_{bot_id}" in l.lower() or f"bot_id={bot_id}" in l]
                if not bot_lines:
                    # Return last N lines if no bot-specific logs
                    return "".join(all_lines[-lines:])
                return "".join(bot_lines[-lines:])
        except Exception:
            return None
    
    def _get_status_file_path(self, bot_id: int) -> Path:
        """获取 bot 状态文件路径"""
        return self._project_root / "status" / f"bot_{bot_id}.json"
    
    def read_bot_status(self, bot_id: int) -> Optional[Dict[str, Any]]:
        """
        从状态文件读取 bot 详细运行状态
        
        状态文件由 bot 进程在每个周期结束时写入。
        
        Args:
            bot_id: Bot ID
            
        Returns:
            状态字典，包含 cycle, balance, positions 等信息
        """
        status_file = self._get_status_file_path(bot_id)
        
        if not status_file.exists():
            return None
        
        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    
    def get_bot_full_status(self, bot_id: int) -> Dict[str, Any]:
        """
        获取 bot 完整状态（合并进程信息和状态文件）
        
        Args:
            bot_id: Bot ID
            
        Returns:
            完整状态字典
        """
        result = {
            "bot_id": bot_id,
            "is_running": self.is_running(bot_id),
            "process_info": None,
            "runtime_status": None,
        }
        
        # 进程信息
        process_info = self.get_process_info(bot_id)
        if process_info:
            result["process_info"] = process_info
        
        # 运行时状态（从状态文件读取）
        status = self.read_bot_status(bot_id)
        if status:
            result["runtime_status"] = status
            # 同步一些关键信息到顶层
            result["cycle"] = status.get("cycle", 0)
            result["balance"] = status.get("balance", 0)
            result["positions_count"] = status.get("positions_count", 0)
            result["state"] = status.get("state", "unknown")
            result["last_decision"] = status.get("last_decision")
            result["last_error"] = status.get("last_error")
            result["updated_at"] = status.get("updated_at")
        
        return result


# Global instance
bot_manager = BotManager()

