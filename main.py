from src.LangTrader.utils import logger
from src.LangTrader.market import CryptoFetcher
from src.LangTrader.hyperliquidExchange import hyperliquidAPI
from time import sleep
from src.LangTrader.config import Config
from src.LangTrader.ai.decision_engine import DecisionEngine, DecisionEngineState
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

console = Console()





def main():
    """
    logger.info("Hello from LangTrader!")
    fetcher = CryptoFetcher(symbol="BTC")
    current_price = fetcher.get_current_price()
    df = fetcher.get_OHLCV()
    df = fetcher.get_technical_indicators(df)
    simple_prompt = fetcher.get_simple_trade_signal(df)
    #get the hyperliquid API
    hyperliquid = hyperliquidAPI()
    account_balance = hyperliquid.get_account_balance()
    test_order = hyperliquid.test_order("BTC")
    logger.info(f"Test order result: {test_order}")
    sleep(20)
    close_all_positions = hyperliquid.close_all_positions()
    logger.info(f"Close all positions result: {close_all_positions}")
    """
    """ Strarting LLM test """
    config = Config(trader_id="bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    decision_engine = DecisionEngine(config)
    state = DecisionEngineState(
        trader_id=config.trader_id,
        symbol="",  # 初始为空，workflow 中会填充
        market_data="",  # str 类型
        postion_info={},
        action="HOLD",  # str 类型
        side="none",  # 添加 side 字段
        risk_passed=False,
        confidence=0.0,
        leverage=1,  # 默认1倍杠杆
        historical_performance={},  # 初始为空字典
        llm_analysis="",
    )
    result = decision_engine.run(state)
    
    # 美化输出
    console.print("\n")
    
    # 创建决策摘要表格
    table = Table(
        title="🤖 AI Trading Decision 🤖", 
        box=box.DOUBLE,
        title_style="bold magenta",
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue"
    )
    
    table.add_column("字段", style="cyan bold", no_wrap=True, width=20)
    table.add_column("值", style="white")
    
    # Symbol
    table.add_row("📊 Symbol", f"[bold yellow]{result['symbol']}[/bold yellow]")
    
    # Action（动作着色）
    action = result['action']
    if action == 'BUY':
        action_text = f"[bold green]🟢 {action}[/bold green]"
    elif action == 'SELL':
        action_text = f"[bold red]🔴 {action}[/bold red]"
    else:
        action_text = f"[bold yellow]🟡 {action}[/bold yellow]"
    table.add_row("🎯 Action", action_text)
    
    # Side（方向）
    side = result['side']
    side_icon = "📈" if side == 'long' else "📉" if side == 'short' else "⏸️"
    table.add_row("Direction", f"{side_icon} [bold white]{side.upper()}[/bold white]")
    
    # Confidence（置信度着色）
    confidence = result['confidence']
    if confidence > 0.7:
        conf_text = f"[bold green]{confidence:.1%} 🔥[/bold green]"
    elif confidence > 0.4:
        conf_text = f"[bold yellow]{confidence:.1%} ⚠️[/bold yellow]"
    else:
        conf_text = f"[bold red]{confidence:.1%} ❄️[/bold red]"
    table.add_row("💯 Confidence", conf_text)
    
    # Leverage
    leverage_text = f"[bold cyan]{result['leverage']}x[/bold cyan]"
    table.add_row("⚡ Leverage", leverage_text)
    
    # Historical Performance（历史表现）
    hist = result['historical_performance']
    win_rate = hist['win_rate']
    if win_rate > 0.6:
        wr_text = f"[bold green]✅ {win_rate:.1%}[/bold green]"
    elif win_rate > 0.4:
        wr_text = f"[bold yellow]⚠️ {win_rate:.1%}[/bold yellow]"
    else:
        wr_text = f"[bold red]❌ {win_rate:.1%}[/bold red]"
    
    trades_summary = f"[dim]({hist['winning_positions']} ✓ / {hist['losing_positions']} ✗)[/dim]"
    table.add_row("📊 Win Rate", f"{wr_text} {trades_summary}")
    
    # 显示表格
    console.print(table)
    
    # 分析理由用 Panel 显示
    analysis_panel = Panel(
        result['llm_analysis'],
        title="💭 [bold cyan]Decision Analysis[/bold cyan]",
        border_style="blue",
        padding=(1, 2),
        expand=False
    )
    console.print(analysis_panel)
    console.print("\n")

import time

if __name__ == "__main__":
    while True:
        main()
        time.sleep(60 * 5)  # 每5分钟执行一次
