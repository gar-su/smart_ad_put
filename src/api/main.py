from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.api.routers import dashboard, lifecycle, signals

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


app.include_router(lifecycle.router, prefix="/api/lifecycle", tags=["生命周期"])
app.include_router(signals.router, prefix="/api/signals", tags=["建造信号"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["看板"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.API_HOST, port=settings.API_PORT)
