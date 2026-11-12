# КлимаКлас

**Мрежа от сензори за въздуха в класните стаи.** Евтини сензорни възли (ESP32-S3 + сензор за CO₂) мерят CO₂, температура и влажност всяка минута и пращат данните към облачен сървър. Уеб панелът показва всяка стая на живо и праща известие на учителя („Отворете прозореца в стая 214“), когато CO₂ е над 1200 ppm повече от 5 минути.

Проект за НОИТ 2026/2027, направление „Разпределени приложения“. Лиценз: GNU GPL v3.

## Архитектура

```
 Сензорен възел            Шлюз (по избор)          Облачен сървър (VPS)              Уеб панел
┌─────────────────┐  MQTT  ┌───────────────┐ HTTPS ┌──────────────────────────┐ WS  ┌──────────────┐
│ ESP32-S3        │───────▶│ Raspberry Pi  │──────▶│ Caddy (HTTPS)            │────▶│ Vue + Chart.js│
│ STCC4 + SHT40   │        │ Mosquitto +   │       │ FastAPI (REST + WebSocket)│     │ админ /      │
│ OLED дисплей    │        │ SQLite буфер  │       │ PostgreSQL               │     │ директор /   │
└─────────────────┘        └───────────────┘       └──────────────────────────┘     │ учител       │
        └──────────── или директно по HTTPS ──────────────▲          │               └──────────────┘
                                                                     ▼
                                                        Известия: имейл / Telegram
```

| Папка | Какво има |
|-------|-----------|
| [`firmware/`](firmware/) | PlatformIO проект за ESP32-S3 (C++/Arduino) |
| [`gateway/`](gateway/) | Raspberry Pi шлюз: MQTT → устойчива опашка → API |
| [`backend/`](backend/) | FastAPI сървър, база данни, известия, тестове |
| [`frontend/`](frontend/) | Уеб панел (Vue 3 + Chart.js), тъмна/светла тема, мобилна версия |
| `render.yaml`, `Dockerfile` | Публикуване в Render |
| [`deploy/`](deploy/), `docker-compose.yml` | Публикуване на собствен сървър с Docker Compose + Caddy |
| [`docs/`](docs/) | Поръчка на части, схема на свързване |

## Бърз старт (на собствения компютър)

Трябват Python 3.11+ и Node.js 20+.

```bash
# 1) Сървър
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m app.seed            # демо училище + 7 дни данни + тестови акаунти
uvicorn app.main:app --reload # http://localhost:8000/api/docs

# 2) Уеб панел (в друг терминал)
cd frontend
npm install
npm run dev                   # http://localhost:5173

# 3) Симулирани сензори за демо (в трети терминал)
cd backend && source .venv/bin/activate
python scripts/simulate.py --interval 5 --spike 214   # стая 214 „се задушава“
```

### Тестови акаунти

| Роля | Имейл | Парола |
|------|-------|--------|
| Администратор | `admin@klimaklas.test` | `KlimaKlas-2026` |
| Директор | `direktor@klimaklas.test` | `KlimaKlas-2026` |
| Учител (стаи 101 и 214) | `uchitel@klimaklas.test` | `KlimaKlas-2026` |

На публичния сървър паролата се задава с `KK_DEMO_PASSWORD`.

## Роли

- **Администратор** – училища, стаи, устройства (токени), потребители; вижда всичко.
- **Директор** – цялото си училище, седмични отчети, експорт в CSV.
- **Учител** – само своите стаи; получава известия и ги потвърждава („Отворих прозореца“).

## REST API

Пълната документация е на `/api/docs` (Swagger). Основните пътища:

| Метод | Път | Кой |
|-------|-----|-----|
| `POST` | `/api/v1/readings` · `/api/v1/readings/batch` | устройство (Bearer токен) |
| `POST` | `/api/v1/auth/login` · `/logout` · `GET /me` | всички |
| `GET` | `/api/v1/rooms` · `/rooms/{id}` · `/rooms/{id}/readings` · `/rooms/{id}/export.csv` | според ролята |
| `GET` | `/api/v1/alerts` · `POST /alerts/{id}/ack` | според ролята |
| `GET` | `/api/v1/reports/weekly?format=json\|csv` | директор, админ |
| `*` | `/api/v1/schools` · `/devices` · `/users` · `/rooms` | админ |
| `WS` | `/api/v1/ws` | стойности на живо |

## Сигурност

| Заплаха | Защита |
|---------|--------|
| Подслушване | HTTPS навсякъде (Caddy + Let's Encrypt); ESP32 проверява сертификата |
| Изтичане на пароли | bcrypt (cost 12); еднакъв отговор и време при грешен имейл/парола |
| Откраднат токен на устройство | В базата е само SHA-256 хешът; токенът се показва веднъж и може да се смени |
| Налучкване на пароли | Rate limiting: 5 опита за вход в минута от IP; 30 заявки в минута от устройство |
| SQL injection | Само параметризирани заявки чрез SQLAlchemy ORM |
| XSS | Vue екранира всичко; имената не приемат `<` `>`; строг Content-Security-Policy |
| CSRF | Бисквитка `SameSite=Strict` + double-submit CSRF токен в хедър |
| Кражба на сесия | `HttpOnly` + `Secure` бисквитка, JWT с изтичане |
| Cross-Site WebSocket Hijacking | Проверка на `Origin` при WebSocket |
| Достъп до чужди данни | Проверка на ролята при всяка заявка; 404 вместо 403, за да не се издава кое съществува |
| CSV/формула инжекция | Клетки, започващи с `=`, `+`, `-`, `@`, се екранират |
| Невалидни данни от сензор | Строга валидация (обхват, непознати полета, време в бъдещето) |

Всичко това е покрито с автоматични тестове (`backend/tests/`).

## Тестове

```bash
cd backend && pytest -v        # 52 теста: вход, роли, валидация, известия, сигурност, WebSocket
cd gateway && pytest -v        # опашка и препращане при прекъсване на интернета
```

GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) пуска при всеки push тестовете, линтера (ruff, вкл. проверки за сигурност), демо данните върху PostgreSQL, сборката на панела и компилацията на фърмуера.

## Хардуер

Списък с части и схема на свързване: [`docs/porachka.md`](docs/porachka.md).

```bash
cd firmware
cp include/secrets.example.h include/secrets.h   # Wi-Fi, адрес на API, токен на устройството
pio run -e esp32s3 -t upload && pio device monitor
```

Токен за устройство се взима от **Администрация → Устройства → Регистрирай устройство**.

Ако в училището има Raspberry Pi, в `include/config.h` задайте `USE_MQTT_GATEWAY 1`. Инсталация на шлюза: [`gateway/README.md`](gateway/README.md).

## Публикуване в Render (безплатно)

Репото съдържа [`render.yaml`](render.yaml) и [`Dockerfile`](Dockerfile): една уеб услуга сервира API-то и панела, а базата е PostgreSQL на Render. Стъпките са в [`docs/deploy-render.md`](docs/deploy-render.md).

## Публикуване на собствен VPS

```bash
git clone <repo> klimaklas && cd klimaklas
cp .env.example .env && nano .env      # домейн, пароли, KK_SECRET_KEY
docker compose up -d --build
docker compose exec backend python -m app.seed
```

Насочете DNS записа (A) на домейна към IP адреса на сървъра. Caddy ще вземе HTTPS сертификат сам.
