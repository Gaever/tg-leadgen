# Telegram LeadGen Service

Сервис для скачивания сообщений из Telegram чатов и поиска по ним через RAG (Retrieval-Augmented Generation).

## 🚀 Возможности

- **Веб-интерфейс как в Telegram** — список чатов с поддержкой форумов (каталогов чатов)
- **Скачивание сообщений** — с настройкой лимитов и пагинации
- **RAG поиск** — семантический поиск по скачанным сообщениям
- **Метаданные** — сохранение ID авторов, сообщений, дат и другой информации
- **Docker-инфраструктура** — все поднимается локально через docker-compose

## 📋 Требования

- Docker и Docker Compose
- Telegram API credentials (получить на https://my.telegram.org/apps)
- OpenAI API ключ (для эмбеддингов)

## ⚡ Быстрый старт

### 1. Клонирование и настройка

```bash
# Перейти в директорию проекта
cd telegram-leadgen

# Создать .env файл
cp .env.example .env

# Отредактировать .env и заполнить переменные:
# - TELEGRAM_API_ID
# - TELEGRAM_API_HASH  
# - TELEGRAM_PHONE (ваш номер телефона)
# - OPENAI_API_KEY
```

### 2. Запуск

```bash
docker compose up --build
```

### 3. Доступ к интерфейсу

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **QDrant UI**: http://localhost:6333/dashboard

## 📱 Использование

### Авторизация в Telegram

1. Откройте http://localhost:3000
2. Нажмите "Войти в Telegram"
3. Введите код из Telegram
4. При необходимости введите пароль 2FA

### Скачивание сообщений

1. Выберите чат из списка
2. Если это форум — выберите топик
3. Настройте параметры:
   - **Количество сообщений** — сколько скачать
   - **Offset ID** — с какого сообщения начать (0 = с последнего)
   - **Min/Max ID** — диапазон ID сообщений
4. Нажмите "Скачать"

### RAG Поиск

1. Перейдите во вкладку "Поиск" (иконка лупы)
2. Выберите источники (скачанные чаты)
3. Введите запрос, например:
   - "найди посты авторов про онлайн школы"
   - "сообщения о маркетинге"
   - "авторы которые продают курсы"
4. Результаты показывают оригинальные сообщения с метаданными

## 🏗️ Архитектура

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│    Backend      │────▶│    QDrant       │
│   (React/Vite)  │     │   (FastAPI)     │     │ (Vector Store)  │
│   :3000         │     │   :8000         │     │   :6333         │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  Telegram API   │
                        │   (Telethon)    │
                        └─────────────────┘
```

### Компоненты

- **Frontend** — React + Vite + TailwindCSS
- **Backend** — FastAPI + Telethon
- **Vector DB** — QDrant для хранения эмбеддингов
- **Embeddings** — OpenAI text-embedding-3-small

## 📁 Структура проекта

```
telegram-leadgen/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── models.py
│       ├── telegram_client.py
│       ├── rag_service.py
│       └── routes/
│           ├── chats.py
│           ├── messages.py
│           └── rag.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── components/
│       │   ├── ChatsPage.jsx
│       │   ├── AuthModal.jsx
│       │   ├── DownloadModal.jsx
│       │   └── RAGPage.jsx
│       └── styles/
│           └── index.css
└── data/
    └── messages/
```

## 🔧 API Endpoints

### Авторизация
- `GET /api/chats/auth/status` — статус авторизации
- `POST /api/chats/auth/send-code` — отправить код
- `POST /api/chats/auth/verify-code` — подтвердить код
- `POST /api/chats/auth/verify-2fa` — подтвердить 2FA

### Чаты
- `GET /api/chats/` — список чатов
- `GET /api/chats/{chat_id}/topics` — топики форума

### Сообщения
- `POST /api/messages/download` — скачать и индексировать (streaming)
- `GET /api/messages/stats` — статистика

### RAG
- `GET /api/rag/sources` — доступные источники
- `POST /api/rag/search` — поиск по сообщениям
- `GET /api/rag/stats` — статистика RAG

## 💡 Примеры запросов RAG

```json
{
  "query": "авторы которые пишут про онлайн школы",
  "sources": [123456789, 987654321],
  "top_k": 10
}
```

Ответ содержит оригинальные сообщения:
```json
{
  "results": [
    {
      "message": {
        "id": 12345,
        "chat_id": 123456789,
        "author": {
          "id": 111222333,
          "username": "example_user"
        },
        "text": "Текст сообщения...",
        "date": "2024-01-15T12:00:00"
      },
      "score": 0.92
    }
  ]
}
```

## 🔒 Безопасность

- Telegram сессия сохраняется в Docker volume
- API ключи хранятся в .env файле (не коммитьте!)
- Рекомендуется использовать только в локальной сети

## 🐛 Troubleshooting

### "Not authorized in Telegram"
Пройдите авторизацию через веб-интерфейс.

### "Flood wait"
Telegram ограничивает частоту запросов. Подождите указанное время.

### "Connection error"
Проверьте что все контейнеры запущены: `docker-compose ps`

### QDrant не запускается
Убедитесь что порты 6333 и 6334 свободны.

## 📄 Лицензия

MIT
