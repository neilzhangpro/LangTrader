# packages/langtrader_core/services/llm_factory.py

from typing import Optional
from langtrader_core.utils import get_logger
from langchain_core.language_models import BaseChatModel

logger = get_logger("llm_factory")

try:
    from langchain_openai import ChatOpenAI
    from langchain_anthropic import ChatAnthropic
    from langchain_ollama import ChatOllama
except ImportError as e:
    logger.warning(f"LangChain导入失败: {e}")
    ChatOpenAI = None
    ChatAnthropic = None
    ChatOllama = None

from sqlmodel import Session

from langtrader_core.data.repositories.llm_config import LLMConfigRepository
from langtrader_core.data.models.llm_config import LLMConfig




class LLMFactory:
    """
    LLM 工厂类
    根据配置创建不同的 LLM 实例
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.repo = LLMConfigRepository(session)
    
    def create_from_config(self, config: LLMConfig) -> BaseChatModel:
        """
        根据配置创建 LLM 实例
        """
        if not config.is_enabled:
            logger.error(f"🙅 LLM config '{config.name}' is disabled")
            raise ValueError(f"LLM config '{config.name}' is disabled")
        
        provider = config.provider.lower()
        kwargs = config.to_langchain_kwargs()
        
        logger.info(f"Creating LLM: {config.display_name or config.name} ({config.provider}/{config.model_name})")
        logger.debug(f"LLM kwargs: {kwargs}")
        
        if provider == "openai":
            if not ChatOpenAI:
                logger.error("🙅 OpenAI 未安装")
                raise ValueError("OpenAI 未安装")
            return ChatOpenAI(**kwargs)
        
        elif provider == "anthropic":
            if not ChatAnthropic:
                logger.error("🙅 Anthropic 未安装")
                raise ValueError("Anthropic 未安装")
            return ChatAnthropic(**kwargs)
        
        elif provider == "ollama":
            # Ollama 本地模型
            if not ChatOllama:
                logger.error("🙅 Ollama 未安装")
                raise ValueError("Ollama 未安装")
            return ChatOllama(**kwargs)
        
        else:
            # other models can try using openai api first
            try:
                return ChatOpenAI(**kwargs)
            except Exception as e:
                logger.error(f"Failed to create LLM: {e}")
                raise ValueError(f"Failed to create LLM: {e}")
    
    def create_from_id(self, config_id: int) -> BaseChatModel:
        """根据配置 ID 创建 LLM"""
        config = self.repo.get_by_id(config_id)
        if not config:
            raise ValueError(f"LLM config not found: id={config_id}")
        return self.create_from_config(config)
    
    def create_from_name(self, name: str) -> BaseChatModel:
        """根据配置名称创建 LLM"""
        config = self.repo.get_by_name(name)
        if not config:
            raise ValueError(f"LLM config not found: name={name}")
        return self.create_from_config(config)
    
    def create_default(self) -> BaseChatModel:
        """创建默认 LLM"""
        config = self.repo.get_default()
        if not config:
            raise ValueError("No default LLM config found")
        return self.create_from_config(config)
    
    def create_for_bot(self, bot_id: int, session: Optional[Session] = None) -> BaseChatModel:
        """
        为指定 Bot 创建 LLM
        优先使用 Bot 配置的 LLM，否则使用默认 LLM
        """
        from langtrader_core.data.repositories.bot import BotRepository
        
        bot_session = session or self.session
        bot_repo = BotRepository(bot_session)
        bot = bot_repo.get_by_id(bot_id)
        
        if not bot:
            raise ValueError(f"Bot not found: id={bot_id}")
        
        # 优先使用 Bot 配置的 LLM
        if bot.llm_id:
            logger.info(f"Using bot-specific LLM: bot_id={bot_id}, llm_id={bot.llm_id}")
            return self.create_from_id(bot.llm_id)
        
        # 否则使用默认 LLM
        logger.info(f"Using default LLM for bot: bot_id={bot_id}")
        return self.create_default()