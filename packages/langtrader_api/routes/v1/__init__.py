"""
API v1 Routes

所有 API 路由注册：
- health: 健康检查
- auth: 认证
- bots: Bot 管理
- trades: 交易历史
- performance: 绩效分析
- backtests: 回测管理
- workflows: 工作流管理
- exchanges: 交易所配置
- llm-configs: LLM 配置
- system-configs: 系统配置
- dashboard: Dashboard 聚合数据
- docs: 文档
"""
from fastapi import APIRouter

from langtrader_api.routes.v1.health import router as health_router
from langtrader_api.routes.v1.auth import router as auth_router
from langtrader_api.routes.v1.bots import router as bots_router
from langtrader_api.routes.v1.trades import router as trades_router
from langtrader_api.routes.v1.performance import router as performance_router
from langtrader_api.routes.v1.backtests import router as backtests_router
from langtrader_api.routes.v1.workflows import router as workflows_router
from langtrader_api.routes.v1.exchanges import router as exchanges_router
from langtrader_api.routes.v1.llm_configs import router as llm_configs_router
from langtrader_api.routes.v1.system_configs import router as system_configs_router
from langtrader_api.routes.v1.dashboard import router as dashboard_router
from langtrader_api.routes.v1.docs import router as docs_router

router = APIRouter()

# Include all routers
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(bots_router)
router.include_router(trades_router)
router.include_router(performance_router)
router.include_router(backtests_router)
router.include_router(workflows_router)
router.include_router(exchanges_router)
router.include_router(llm_configs_router)
router.include_router(system_configs_router)
router.include_router(dashboard_router)
router.include_router(docs_router)

