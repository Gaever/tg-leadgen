from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.routes import chats, messages, rag
from app.telegram_client import telegram_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await telegram_service.connect()
    yield
    # Shutdown
    await telegram_service.disconnect()


app = FastAPI(
    title="Telegram LeadGen Service",
    description="Сервис для скачивания сообщений из Telegram и поиска по ним через RAG",
    version="1.0.0",
    lifespan=lifespan
)

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(rag.router)


@app.get("/")
async def root():
    return {
        "service": "Telegram LeadGen",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
