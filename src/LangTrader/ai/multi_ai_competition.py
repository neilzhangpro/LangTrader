# simper-trader/src/LangTrader/ai/multi_ai_competition.py
from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI
from langchain.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from src.LangTrader.utils import logger
from src.LangTrader.config import Config
from typing import List, Dict
import json

class TradingDecision(BaseModel):
    """AI决策结构"""
    symbol: str = Field(description="选择的交易币种")
    action: str = Field(description="交易动作: BUY, SELL, 或 HOLD")
    side: str = Field(description="方向: long 或 short，HOLD为none")
    confidence: float = Field(description="决策置信度 0.0-1.0", ge=0.0, le=1.0)
    leverage: int = Field(description="建议杠杆倍数 1-10", ge=1, le=10)
    analysis: str = Field(description="决策分析理由")

class MultiAICompetition:
    """
    🤖🤖🤖 多AI竞争模块
    
    同时调用多个AI模型进行决策竞争，选择置信度最高的决策
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.db = config.db
        
        # 配置多个AI模型
        self.models = self._initialize_models()
    
    def _initialize_models(self) -> Dict[str, any]:
        """
        初始化多个AI模型
        
        注意：需要在 config.json 中添加模型配置
        """
        models = {}
        
        # Claude Sonnet 4（主模型）
        try:
            anthropic_config = self.config.llm_config.get("anthropic", {})
            models['claude'] = init_chat_model(
                model=anthropic_config.get("model", "claude-sonnet-4-20250514"),
                api_key=anthropic_config.get("api_key"),
                base_url = anthropic_config.get("base_url"),
                temperature=0.2
            )
            logger.info("✅ Claude Sonnet 4 已加载")
        except Exception as e:
            logger.error(f"❌ Claude加载失败: {e}")
        
        # DeepSeek V3
        try:
            deepseek_config = self.config.llm_config.get("deepseek", {})
            models['deepseek'] = ChatOpenAI(
                model=deepseek_config.get("model", "deepseek-chat"),
                api_key=deepseek_config.get("api_key"),
                base_url=deepseek_config.get("base_url"),
                temperature=0.2
            )
            logger.info("✅ DeepSeek V3 已加载")
        except Exception as e:
            logger.error(f"❌ DeepSeek加载失败: {e}")
        
        # GPT-4o
        try:
            openai_config = self.config.llm_config.get("openai", {})
            models['gpt4o'] = init_chat_model(
                model=openai_config.get("model","gtp-4o"),
                api_key=openai_config.get("api_key"),
                base_url=openai_config.get("base_url"),
                temperature=0.2
            )
            logger.info("✅ GPT-4o 已加载")
        except Exception as e:
            logger.error(f"❌ GPT-4o加载失败: {e}")
        
        
        if not models:
            logger.error("❌ 没有可用的AI模型！")
            raise RuntimeError("至少需要一个AI模型")
        
        logger.info(f"🤖 已加载 {len(models)} 个AI模型: {list(models.keys())}")
        return models
    
    def run_competition(self, system_prompt: str, user_prompt: str, trader_id: str) -> Dict:
        """
        🏆 运行AI竞争
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词（包含市场数据）
            trader_id: 交易者ID
        
        Returns:
            {
                'winner_model': 'claude',
                'winner_decision': {...},
                'all_decisions': {...},
                'competition_id': 'uuid'
            }
        """
        logger.info("🤖🤖🤖 -----Start Multi-AI Competition------")
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        logger.info(f"Messages: {messages}")

        all_decisions = {}
        
        # 1. 让所有AI模型同时做出决策
        for model_name, model in self.models.items():
            try:
                logger.info(f"🧠 正在调用 {model_name.upper()}...")
                
                structured_llm = model.with_structured_output(TradingDecision)
                decision = structured_llm.invoke(messages)
                
                all_decisions[model_name] = {
                    'symbol': decision.symbol,
                    'action': decision.action,
                    'side': decision.side,
                    'confidence': decision.confidence,
                    'leverage': decision.leverage,
                    'analysis': decision.analysis
                }
                
                logger.info(
                    f"   {model_name.upper()}: "
                    f"{decision.action} {decision.symbol} {decision.side} "
                    f"@ confidence {decision.confidence:.2f}"
                )
                
            except Exception as e:
                logger.error(f"❌ {model_name} 决策失败: {e}")
                all_decisions[model_name] = {
                    'symbol': '',
                    'action': 'HOLD',
                    'side': 'none',
                    'confidence': 0.0,
                    'leverage': 1,
                    'analysis': f'模型调用失败: {str(e)}'
                }
        
        # 2. 选择置信度最高的决策
        winner_model = max(
            all_decisions.items(),
            key=lambda x: x[1]['confidence']
        )[0]
        
        winner_decision = all_decisions[winner_model]
        
        logger.info(f"\n🏆 竞争结果:")
        sorted_models = sorted(
            all_decisions.items(),
            key=lambda x: x[1]['confidence'],
            reverse=True
        )
        for rank, (model, decision) in enumerate(sorted_models, 1):
            icon = "✅" if model == winner_model else ""
            logger.info(
                f"   {rank}. {model.upper()}: "
                f"confidence={decision['confidence']:.2f} {icon}"
            )
        
        # 3. 存储竞争记录到数据库
        competition_id = self._store_competition(
            trader_id, all_decisions, winner_model, winner_decision
        )
        
        # 4. 更新AI模型表现统计
        self._update_model_performance(trader_id, all_decisions, winner_model)
        
        logger.info(f"💾 竞争记录已存储，ID: {competition_id}")
        logger.info("🤖🤖🤖 -----End Multi-AI Competition------\n")
        
        return {
            'winner_model': winner_model,
            'winner_decision': winner_decision,
            'all_decisions': all_decisions,
            'competition_id': competition_id
        }
    
    def _store_competition(
        self, trader_id: str, all_decisions: Dict, 
        winner_model: str, winner_decision: Dict
    ) -> str:
        """存储竞争记录到数据库"""
        try:
            result = self.db.execute("""
                INSERT INTO ai_competitions
                (trader_id, models_competed, winner_model, 
                 winner_confidence, winner_decision)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (
                trader_id,
                json.dumps(all_decisions),
                winner_model,
                winner_decision['confidence'],
                json.dumps(winner_decision)
            ))
            
            return result[0]['id'] if result else None
            
        except Exception as e:
            logger.error(f"❌ 存储竞争记录失败: {e}")
            return None
    
    def _update_model_performance(
        self, trader_id: str, all_decisions: Dict, winner_model: str
    ):
        """更新AI模型表现统计"""
        try:
            for model_name, decision in all_decisions.items():
                times_selected = 1 if model_name == winner_model else 0
                confidence = decision['confidence']
                
                self.db.execute("""
                    INSERT INTO ai_model_performance
                    (trader_id, model_name, total_competitions, times_selected, 
                     avg_confidence, last_updated)
                    VALUES (%s, %s, 1, %s, %s, NOW())
                    ON CONFLICT (trader_id, model_name)
                    DO UPDATE SET
                        total_competitions = ai_model_performance.total_competitions + 1,
                        times_selected = ai_model_performance.times_selected + EXCLUDED.times_selected,
                        selection_rate = (ai_model_performance.times_selected + EXCLUDED.times_selected) * 100.0 
                                       / (ai_model_performance.total_competitions + 1),
                        avg_confidence = (ai_model_performance.avg_confidence * ai_model_performance.total_competitions + %s)
                                       / (ai_model_performance.total_competitions + 1),
                        last_updated = NOW()
                """, (trader_id, model_name, times_selected, confidence, confidence))
            
            logger.info("✅ AI模型表现统计已更新")
            
        except Exception as e:
            logger.error(f"❌ 更新模型表现失败: {e}")