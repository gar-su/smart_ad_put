from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

app = FastAPI(
    title="Smart Ad Put API",
    description="智能广告基建系统 - 决策指挥中心",
    version="0.1.0",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# 路由将在后续添加
from src.api.routers import lifecycle, automation, strategy, dashboard

app.include_router(lifecycle.router, prefix="/api/lifecycle", tags=["生命周期"])
app.include_router(automation.router, prefix="/api/automation", tags=["自动化"])
app.include_router(strategy.router, prefix="/api/strategy", tags=["策略"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["看板"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
