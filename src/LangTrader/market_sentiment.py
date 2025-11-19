"""
市场情绪和外部数据获取模块

提供以下数据源：
1. 恐慌贪婪指数 (Fear & Greed Index)
2. 加密货币新闻 (Crypto News)
3. 资金费率 (Funding Rate)
4. 社交媒体情绪 (Social Sentiment) - 可选

作者: 大王的大(Tomie)
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.LangTrader.utils import logger
import time
import os
import feedparser
from dotenv import load_dotenv
load_dotenv()


class MarketSentiment:
    """市场情绪数据获取器"""
    
    def __init__(self):
        self.cache = {}  # 简单的内存缓存
        self.cache_duration = 300  # 5分钟缓存
        self.request_timeout = 10  # 请求超时时间（秒）
        
        logger.info("✅ MarketSentiment 模块初始化完成 (使用RSS+Reddit免费源)")
    
    def get_all_sentiment_data(self, symbol: str) -> Dict:
        """
        获取所有情绪数据（一次性调用）
        
        Args:
            symbol: 交易对符号，如 'BTC', 'ETH'
            
        Returns:
            包含所有情绪数据的字典
        """
        logger.info(f"📊 开始获取 {symbol} 的市场情绪数据...")
        
        data = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "fear_greed_index": self.get_fear_greed_index(),
            "funding_rate": self.get_funding_rate(symbol),
            "market_overview": self.get_market_overview()
        }
        
        logger.info(f"✅ {symbol} 情绪数据获取完成")
        return data
    
    def get_global_news(self, limit: int = 5) -> List[Dict]:
        """
        获取全局加密货币市场新闻（不区分币种）
        
        Args:
            limit: 返回新闻数量
            
        Returns:
            新闻列表
        """
        return self.get_recent_news("", limit)
    
    def get_fear_greed_index(self) -> Dict:
        """
        获取恐慌贪婪指数
        
        数据源: https://alternative.me/crypto/fear-and-greed-index/
        免费，无需API Key
        
        Returns:
            {
                "value": int (0-100),
                "classification": str ("Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"),
                "interpretation": str (中文解读)
            }
        """
        cache_key = "fear_greed_index"
        
        # 检查缓存
        if self._is_cache_valid(cache_key):
            logger.info("📦 使用缓存的恐慌贪婪指数")
            return self.cache[cache_key]["data"]
        
        try:
            logger.info("🌐 正在从 Alternative.me 获取恐慌贪婪指数...")
            
            response = requests.get(
                "https://api.alternative.me/fng/",
                params={"limit": 1},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if "data" in data and len(data["data"]) > 0:
                    fng_data = data["data"][0]
                    value = int(fng_data["value"])
                    
                    result = {
                        "value": value,
                        "classification": fng_data["value_classification"],
                        "interpretation": self._interpret_fng(value),
                        "timestamp": fng_data.get("timestamp", "")
                    }
                    
                    # 缓存结果
                    self._cache_data(cache_key, result)
                    
                    logger.info(f"✅ 恐慌贪婪指数: {value} ({result['classification']})")
                    return result
            
            logger.warning(f"⚠️ Fear & Greed Index API返回状态码: {response.status_code}")
            return self._get_default_fng()
            
        except requests.exceptions.Timeout:
            logger.error("❌ 获取恐慌指数超时")
            return self._get_default_fng()
        except Exception as e:
            logger.error(f"❌ 获取恐慌指数失败: {e}")
            return self._get_default_fng()
    
    def get_recent_news(self, symbol: str, limit: int = 5) -> List[Dict]:
        """
        获取最近的加密货币新闻 - 组合多个免费源
        
        数据源（按优先级）：
        1. RSS订阅（CoinDesk, CoinTelegraph等）- 完全免费
        2. Reddit讨论（r/cryptocurrency等）- 完全免费
        
        Args:
            symbol: 币种符号
            limit: 返回新闻数量
            
        Returns:
            新闻列表
        """
        cache_key = f"news_{symbol}_{limit}"
        
        if self._is_cache_valid(cache_key):
            logger.info(f"📦 使用缓存的 {symbol} 新闻")
            return self.cache[cache_key]["data"]
        
        all_news = []
        
        # 1. 尝试RSS源（优先）
        try:
            logger.debug("📡 尝试RSS源...")
            rss_news = self._get_rss_news(symbol, limit=3)
            all_news.extend(rss_news)
        except Exception as e:
            logger.debug(f"RSS获取失败: {e}")
        
        # 2. 尝试Reddit（补充）
        if len(all_news) < limit:
            try:
                logger.debug("📡 尝试Reddit...")
                reddit_news = self._get_reddit_posts(symbol, limit=2)
                all_news.extend(reddit_news)
            except Exception as e:
                logger.debug(f"Reddit获取失败: {e}")
        
        # 3. 去重（基于标题）
        unique_news = []
        seen_titles = set()
        
        for news in all_news:
            title_key = news["title"][:50].lower()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_news.append(news)
        
        # 缓存结果
        if unique_news:
            self._cache_data(cache_key, unique_news[:limit])
            logger.info(f"✅ 获取到 {len(unique_news[:limit])} 条新闻")
        else:
            logger.warning(f"⚠️ 无法获取 {symbol} 的新闻数据")
        
        return unique_news[:limit]
    
    def _get_rss_news(self, symbol: str, limit: int) -> List[Dict]:
        """从RSS源获取加密货币新闻（完全免费，无限制）"""
        
        # 主流加密货币新闻RSS源
        rss_feeds = {
            "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "CoinTelegraph": "https://cointelegraph.com/rss",
            "Decrypt": "https://decrypt.co/feed",
            "Bitcoin.com": "https://news.bitcoin.com/feed/",
        }
        
        all_news = []
        
        for source_name, feed_url in rss_feeds.items():
            try:
                logger.debug(f"📡 获取 {source_name} RSS...")
                
                feed = feedparser.parse(feed_url)
                
                # 每个源最多取2条
                for entry in feed.entries[:2]:
                    title = entry.get("title", "")
                    
                    # 如果symbol为空，获取所有加密货币新闻
                    # 如果symbol有值，过滤特定币种
                    if not symbol:
                        # 全局新闻：只要包含crypto相关关键词
                        if any(keyword in title.lower() for keyword in ["crypto", "bitcoin", "btc", "ethereum", "eth", "blockchain", "defi"]):
                            should_include = True
                        else:
                            should_include = False
                    else:
                        # 特定币种新闻
                        should_include = (symbol.upper() in title.upper() or 
                                        "crypto" in title.lower() or 
                                        "bitcoin" in title.lower() or
                                        "ethereum" in title.lower())
                    
                    if should_include:
                        # 解析发布时间
                        published = entry.get("published_parsed")
                        published_str = ""
                        if published:
                            try:
                                published_str = datetime(*published[:6]).isoformat()
                            except:
                                published_str = datetime.now().isoformat()
                        
                        all_news.append({
                            "title": title,
                            "description": entry.get("summary", "")[:200] if entry.get("summary") else title[:200],
                            "url": entry.get("link", ""),
                            "published_at": published_str,
                            "source": source_name
                        })
                
            except Exception as e:
                logger.debug(f"❌ {source_name} RSS获取失败: {e}")
                continue
        
        # 按时间排序
        all_news.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        
        logger.debug(f"📰 RSS获取到 {len(all_news)} 条相关新闻")
        return all_news[:limit]
    
    def _get_reddit_posts(self, symbol: str, limit: int) -> List[Dict]:
        """从Reddit获取加密货币讨论（完全免费）"""
        
        try:
            # Reddit公开JSON端点（无需API Key）
            subreddits = ["cryptocurrency", "CryptoMarkets"]
            
            news_list = []
            
            for subreddit in subreddits:
                try:
                    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
                    
                    headers = {
                        "User-Agent": "LangTrader/1.0 (Crypto Trading Bot)"
                    }
                    
                    response = requests.get(url, headers=headers, timeout=self.request_timeout)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        for post in data.get("data", {}).get("children", [])[:10]:
                            post_data = post.get("data", {})
                            title = post_data.get("title", "")
                            
                            # 如果symbol为空，获取所有热门讨论
                            # 如果symbol有值，只获取相关讨论
                            if not symbol or symbol.upper() in title.upper():
                                news_list.append({
                                    "title": title,
                                    "description": post_data.get("selftext", "")[:200] if post_data.get("selftext") else title,
                                    "url": f"https://reddit.com{post_data.get('permalink', '')}",
                                    "published_at": datetime.fromtimestamp(post_data.get("created_utc", 0)).isoformat() if post_data.get("created_utc") else "",
                                    "source": f"r/{subreddit}",
                                    "votes": post_data.get("ups", 0)
                                })
                except Exception as e:
                    logger.debug(f"❌ r/{subreddit} 获取失败: {e}")
                    continue
            
            logger.debug(f"📰 Reddit获取到 {len(news_list)} 条讨论")
            return news_list[:limit]
            
        except Exception as e:
            logger.debug(f"❌ Reddit获取失败: {e}")
            return []
    
    def get_funding_rate(self, symbol: str) -> Dict:
        """
        获取永续合约资金费率
        
        数据源: Binance Futures API (免费)
        资金费率反映多空情绪：
        - 正值：多头支付空头费用（市场看多）
        - 负值：空头支付多头费用（市场看空）
        
        Args:
            symbol: 币种符号
            
        Returns:
            {
                "rate": float (百分比),
                "interpretation": str (解读),
                "next_funding_time": str
            }
        """
        cache_key = f"funding_rate_{symbol}"
        
        if self._is_cache_valid(cache_key):
            logger.info(f"📦 使用缓存的 {symbol} 资金费率")
            return self.cache[cache_key]["data"]
        
        try:
            logger.info(f"🌐 从 Binance 获取 {symbol} 资金费率...")
            
            # Binance合约交易对格式
            binance_symbol = f"{symbol.upper()}USDT"
            
            response = requests.get(
                "https://fapi.binance.com/fapi/v1/fundingRate",
                params={"symbol": binance_symbol, "limit": 1},
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0:
                    funding_rate = float(data[0]["fundingRate"]) * 100  # 转换为百分比
                    funding_time = int(data[0].get("fundingTime", 0))
                    
                    result = {
                        "rate": funding_rate,
                        "rate_formatted": f"{funding_rate:+.4f}%",
                        "interpretation": self._interpret_funding_rate(funding_rate),
                        "next_funding_time": datetime.fromtimestamp(funding_time / 1000).strftime("%Y-%m-%d %H:%M:%S") if funding_time else "",
                        "symbol": binance_symbol
                    }
                    
                    self._cache_data(cache_key, result)
                    
                    logger.info(f"✅ {symbol} 资金费率: {result['rate_formatted']}")
                    return result
            
            logger.warning(f"⚠️ 无法获取 {symbol} 资金费率，可能该币种不支持")
            return self._get_default_funding_rate()
            
        except Exception as e:
            logger.error(f"❌ 获取资金费率失败: {e}")
            return self._get_default_funding_rate()
    
    def get_market_overview(self) -> Dict:
        """
        获取市场概览
        
        包括：
        - 总市值
        - BTC市场占有率
        - 24小时交易量
        
        Returns:
            市场概览数据
        """
        cache_key = "market_overview"
        
        if self._is_cache_valid(cache_key):
            logger.info("📦 使用缓存的市场概览")
            return self.cache[cache_key]["data"]
        
        try:
            logger.info("🌐 从 CoinGecko 获取市场概览...")
            
            response = requests.get(
                "https://api.coingecko.com/api/v3/global",
                timeout=self.request_timeout
            )
            
            if response.status_code == 200:
                data = response.json().get("data", {})
                
                result = {
                    "total_market_cap_usd": data.get("total_market_cap", {}).get("usd", 0),
                    "total_volume_24h_usd": data.get("total_volume", {}).get("usd", 0),
                    "btc_dominance": data.get("market_cap_percentage", {}).get("btc", 0),
                    "eth_dominance": data.get("market_cap_percentage", {}).get("eth", 0),
                    "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd", 0)
                }
                
                self._cache_data(cache_key, result)
                
                logger.info(f"✅ 市场概览: BTC占比 {result['btc_dominance']:.2f}%")
                return result
                
        except Exception as e:
            logger.error(f"❌ 获取市场概览失败: {e}")
        
        return {}
    
    # ========== 辅助方法 ==========
    
    def _interpret_fng(self, value: int) -> str:
        """解读恐慌贪婪指数"""
        if value <= 20:
            return "极度恐慌 - 市场过度悲观，可能是抄底机会，但需谨慎等待企稳信号"
        elif value <= 40:
            return "恐慌 - 市场悲观情绪较重，可考虑分批建仓，设好止损"
        elif value <= 60:
            return "中性 - 市场情绪平稳，技术面分析更为重要"
        elif value <= 80:
            return "贪婪 - 市场乐观情绪较高，注意回调风险，可考虑部分止盈"
        else:
            return "极度贪婪 - 市场过热，警惕顶部风险，建议谨慎追高或减仓"
    
    def _interpret_funding_rate(self, rate: float) -> str:
        """解读资金费率（百分比格式）"""
        if rate > 0.1:
            return "多头严重过热 - 多头支付高额费用，极可能出现回调或反转"
        elif rate > 0.05:
            return "多头过热 - 多头费用较高，注意短期回调风险"
        elif rate > 0.01:
            return "多头占优 - 市场看多情绪较强，趋势向上"
        elif rate > -0.01:
            return "中性 - 多空平衡，市场方向不明确"
        elif rate > -0.05:
            return "空头占优 - 市场看空情绪较强，趋势向下"
        elif rate > -0.1:
            return "空头过热 - 空头费用较高，注意短期反弹可能"
        else:
            return "空头严重过热 - 空头支付高额费用，极可能出现反弹或反转"
    
    def _get_default_fng(self) -> Dict:
        """返回默认的恐慌贪婪指数（数据获取失败时）"""
        return {
            "value": 50,
            "classification": "Neutral",
            "interpretation": "数据暂时无法获取，建议依赖技术分析",
            "timestamp": ""
        }
    
    def _get_default_funding_rate(self) -> Dict:
        """返回默认的资金费率（数据获取失败时）"""
        return {
            "rate": 0,
            "rate_formatted": "N/A",
            "interpretation": "数据暂时无法获取",
            "next_funding_time": "",
            "symbol": ""
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        """检查缓存是否有效"""
        if key not in self.cache:
            return False
        
        cache_time = self.cache[key]["timestamp"]
        current_time = time.time()
        
        is_valid = (current_time - cache_time) < self.cache_duration
        
        if not is_valid:
            logger.debug(f"🗑️ 缓存过期: {key}")
        
        return is_valid
    
    def _cache_data(self, key: str, data):
        """缓存数据"""
        self.cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
        logger.debug(f"💾 数据已缓存: {key}")
    
    def clear_cache(self, key: Optional[str] = None):
        """
        清除缓存
        
        Args:
            key: 指定的缓存键，如果为None则清除所有缓存
        """
        if key:
            if key in self.cache:
                del self.cache[key]
                logger.info(f"🗑️ 已清除缓存: {key}")
        else:
            self.cache.clear()
            logger.info("🗑️ 已清除所有缓存")


# ========== 工具函数 ==========

def format_sentiment_summary(sentiment_data: Dict) -> str:
    """
    格式化情绪数据摘要（用于日志或展示）
    
    Args:
        sentiment_data: get_all_sentiment_data 返回的数据
        
    Returns:
        格式化的字符串摘要
    """
    lines = [f"\n{'='*50}"]
    lines.append(f"📊 {sentiment_data['symbol']} 市场情绪摘要")
    lines.append(f"{'='*50}")
    
    # 恐慌贪婪指数
    fng = sentiment_data.get("fear_greed_index", {})
    if fng:
        lines.append(f"🎭 恐慌贪婪指数: {fng['value']}/100 ({fng['classification']})")
        lines.append(f"   {fng['interpretation']}")
    
    # 资金费率
    funding = sentiment_data.get("funding_rate", {})
    if funding and funding.get("rate") != 0:
        lines.append(f"\n💰 资金费率: {funding['rate_formatted']}")
        lines.append(f"   {funding['interpretation']}")
    
    # 新闻
    news = sentiment_data.get("news", [])
    if news:
        lines.append(f"\n📰 最近新闻 ({len(news)}条):")
        for i, item in enumerate(news[:3], 1):
            lines.append(f"   {i}. {item['title'][:70]}...")
    
    # 市场概览
    market = sentiment_data.get("market_overview", {})
    if market:
        btc_dom = market.get("btc_dominance", 0)
        if btc_dom:
            lines.append(f"\n🌐 市场概览:")
            lines.append(f"   BTC市场占有率: {btc_dom:.2f}%")
    
    lines.append(f"{'='*50}\n")
    
    return "\n".join(lines)
