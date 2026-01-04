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
    

class BotManager:
    """
    Manages bot processes
    
    Provides start/stop/status operations for trading bots.
    Each bot runs as a separate subprocess.
    """
    
    def __init__(self):
        self._processes: Dict[int, ProcessInfo] = {}
        self._project_root = Path(__file__).parent.parent.parent.parent.parent
    
    def start_bot(self, bot_id: int, dry_run: bool = False) -> bool:
        """
        Start a trading bot as a subprocess
        
        Args:
            bot_id: The bot ID to start
            dry_run: If True, don't execute actual trades
            
        Returns:
            True if started successfully
        """
        if bot_id in self._processes:
            raise ValueError(f"Bot {bot_id} is already running")
        
        # Build command
        script_path = self._project_root / settings.BOT_SCRIPT_PATH
        
        if not script_path.exists():
            raise FileNotFoundError(f"Bot script not found: {script_path}")
        
        # Use uv to run the script
        cmd = ["uv", "run", str(script_path)]
        
        # Add bot_id argument (modify run_once.py to accept this)
        # For now, we'll set it as environment variable
        env = os.environ.copy()
        env["BOT_ID"] = str(bot_id)
        
        if dry_run:
            env["DRY_RUN"] = "1"
        
        # Start process
        process = subprocess.Popen(
            cmd,
            cwd=str(self._project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # Don't create new process group on Windows
            start_new_session=True if os.name != 'nt' else False,
        )
        
        self._processes[bot_id] = ProcessInfo(
            bot_id=bot_id,
            process=process,
            started_at=datetime.now(),
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
            # Process already finished
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
            
            del self._processes[bot_id]
            return True
            
        except Exception as e:
            self._processes[bot_id].error = str(e)
            return False
    
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
        
        process = self._processes[bot_id].process
        
        # Check if process is still alive
        if process.poll() is not None:
            # Process has finished
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
        
        Note: This is a simple implementation that reads from log files.
        In production, consider using a proper logging system.
        """
        log_file = self._project_root / "logs" / "langtrader.log"
        
        if not log_file.exists():
            return None
        
        try:
            with open(log_file, 'r') as f:
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

