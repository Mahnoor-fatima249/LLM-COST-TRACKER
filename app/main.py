from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import auth, track, dashboard, health
from app.routes import subscription
from app.websocket import manager
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routes.auth import decode_token


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="LLM Cost Tracker",
    description="Track and optimize your LLM API costs across multiple providers",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware, requests_per_minute=120)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth.router)
app.include_router(track.router)
app.include_router(dashboard.router)
app.include_router(health.router)
app.include_router(subscription.router)

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        await websocket.close(code=4001)
        return

    await manager.connect(websocket, user_id)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)


@app.get("/")
async def root():
    return FileResponse("frontend/index.html")


@app.get("/api/version")
async def version():
    return {"version": "2.0.0", "name": "LLM Cost Tracker"}
