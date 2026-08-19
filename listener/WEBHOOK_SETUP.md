# Инструкция по настройке webhook для бота MAX Messenger

## Обзор

Сервис `listener` был переведён с long-polling на работу через webhook используя библиотеку `maxapi` с интеграцией FastAPI.

## Архитектура работы webhook

1. **FastAPI сервер** - принимает HTTP POST запросы от платформы MAX
2. **Dispatcher** - обрабатывает входящие события (сообщения, callback, запуск бота)
3. **Bot.subscribe_webhook()** - регистрирует URL вебхука в платформе MAX

## Переменные окружения

Для работы webhook необходимо настроить следующие переменные окружения в файле `.env`:

```bash
# Обязательные переменные
MAX_BOT_TOKEN=ваш_токен_бота

# Webhook конфигурация
WEBHOOK_URL=https://your-domain.com/webhook          # Публичный URL вашего сервера
WEBHOOK_SECRET=ваш_секретный_ключ                    # Секрет для проверки подлинности (5-256 символов)
WEBHOOK_HOST=0.0.0.0                                 # Хост для прослушивания (по умолчанию 0.0.0.0)
WEBHOOK_PORT=8000                                    # Порт сервера (по умолчанию 8000)
WEBHOOK_PATH=/webhook                                # Путь endpoint (по умолчанию /webhook)

# MongoDB
MONGO_URI=mongodb://mongodb:27017/
DB_NAME=maxbot
COLLECTION_NAME=users

# MIS API
MIS_API_URL=https://mis-api-url
MIS_API_KEY=ваш_api_ключ
```

## Как подписать бота на webhook

### Автоматическая подписка (рекомендуется)

При старте приложения автоматически вызывается метод `bot.subscribe_webhook()` через обработчик `@dp.on_started()`:

```python
@dp.on_started()
async def on_dp_started():
    if WEBHOOK_URL:
        await bot.subscribe_webhook(
            url=WEBHOOK_URL,
            update_types=[
                UpdateType.MESSAGE_CREATED,      # Входящие сообщения
                UpdateType.MESSAGE_CALLBACK,     # Нажатия кнопок
                UpdateType.BOT_STARTED,          # Запуск бота
            ],
            secret=WEBHOOK_SECRET,
        )
```

### Ручная подписка через API

Если нужно подписать бота вручную, используйте API MAX:

**Endpoint:** `POST https://dev.max.ru/docs-api/methods/POST/subscriptions`

**Тело запроса:**
```json
{
    "url": "https://your-domain.com/webhook",
    "update_types": [
        "MESSAGE_CREATED",
        "MESSAGE_CALLBACK",
        "BOT_STARTED"
    ]
}
```

**Заголовки:**
```
Authorization: ваш_токен_бота
Content-Type: application/json
```

### Проверка текущих подписок

Получить информацию о текущих подписках можно через метод API:

**Endpoint:** `GET https://dev.max.ru/docs-api/methods/GET/subscriptions`

## Безопасность

### Проверка секрета

При установке `WEBHOOK_SECRET`:
1. Платформа MAX добавляет заголовок `X-Max-Bot-Api-Secret` к каждому запросу
2. FastAPI автоматически проверяет этот заголовок
3. При несоответствии возвращается ошибка `403 Forbidden`

### HTTPS обязателен

Для production среды используйте только HTTPS для `WEBHOOK_URL`.

## Запуск сервиса

### Локально

```bash
# Установите зависимости
pip install -r listener/requirements.txt

# Запустите сервис
python listener/listener.py
```

### Через Docker

```bash
docker-compose up max-listener
```

## Проверка работоспособности

### Health check endpoint

Сервис предоставляет endpoint для проверки работоспособности:

```bash
curl http://localhost:8000/healthz
```

**Ответ:**
```json
{"status": "ok", "webhook_path": "/webhook"}
```

### Логирование

При успешной регистрации webhook в логах появится:
```
INFO - Диспетчер запущен, подписываемся на webhook: https://your-domain.com/webhook
INFO - Подписка на webhook зарегистрирована успешно.
```

## Отписка от webhook

### Автоматически при изменении URL

При изменении `WEBHOOK_URL` и перезапуске сервиса, старая подписка остаётся активной. Нужно либо:

1. **Вручную удалить** через API MAX (DELETE /subscriptions)
2. **Использовать метод** `bot.unsubscribe_webhook(url)`:

```python
await bot.unsubscribe_webhook(url="https://old-url.com/webhook")
```

## Структура обработчиков событий

Все обработчики остаются без изменений и работают как раньше:

```python
@dp.bot_started()
async def bot_started(event: BotStarted):
    # Обработка запуска бота
    pass

@dp.message_created()
async def handle_message(event: MessageCreated):
    # Обработка входящих сообщений
    pass

@dp.message_callback()
async def handle_callback(event: MessageCallback):
    # Обработка нажатий кнопок
    pass

@dp.message_created(ContactFilter())
async def on_contact(event, contact: Contact):
    # Обработка контакта
    pass
```

## Преимущества webhook перед long-polling

1. **Меньше задержка** - события доставляются мгновенно
2. **Меньше нагрузка** - нет постоянных запросов к API
3. **Масштабируемость** - легче масштабировать HTTP сервер
4. **Надёжность** - платформа MAX гарантирует доставку событий

## Troubleshooting

### Webhook не регистрируется

1. Проверьте доступность `WEBHOOK_URL` из интернета
2. Убедитесь, что порт открыт в фаерволе
3. Проверьте логи на наличие ошибок подключения

### События не приходят

1. Проверьте статус подписки через API MAX
2. Убедитесь, что `update_types` включают нужные типы событий
3. Проверьте логи FastAPI сервера

### Ошибка 403 Forbidden

1. Проверьте соответствие `WEBHOOK_SECRET` в приложении и в настройках бота
2. Убедитесь, что заголовок `X-Max-Bot-Api-Secret` передаётся

## Пример полного цикла работы

1. **Запуск сервиса** → Инициализация MongoDB → Старт FastAPI сервера
2. **Lifespan событие** → Вызов `@dp.on_started()` → Регистрация webhook в MAX
3. **Пользователь пишет боту** → MAX отправляет POST на `/webhook` → FastAPI принимает запрос
4. **Dispatcher** → Определяет тип события → Вызывает соответствующий обработчик
5. **Обработчик** → Выполняет логику → Отправляет ответ пользователю
