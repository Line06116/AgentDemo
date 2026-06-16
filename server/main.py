
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="企业知识问答 Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from server.routes.chat import router as chat_router
from server.routes.documents import router as documents_router
from server.routes.extract import router as extract_router
app.include_router(chat_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(extract_router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# 生产模式：serve 前端静态文件
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
