# 🧮 Quipu AI

> **Gerente Virtual para Microempresas** — Un asistente de IA que gestiona inventario y ventas por WhatsApp.

[![CI](https://github.com/yourusername/quipu-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/quipu-ai/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.129+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 ¿Qué es?

Quipu AI es un backend que conecta un **agente LLM** con **WhatsApp Business API** para que bodegueros (dueños de tiendas pequeñas) gestionen su negocio con lenguaje natural:

```
👤 "Vendí 3 arroz a María"
🤖 "✅ Venta registrada: 3x Arroz Extra 1kg a María. Total: S/37.50"

👤 "Cuánto arroz me queda?"
🤖 "Tienes 47 unidades de Arroz Extra 1kg en tu inventario 📦"
```

---

## 🏗️ Arquitectura

```mermaid
graph LR
    WA[📱 WhatsApp] -->|Webhook| META[Meta Cloud API]
    META -->|POST /webhook| API[FastAPI]
    API -->|HMAC-SHA256| SEC{Verificación}
    SEC -->|✅| HIST[Historial]
    HIST --> AGENT[LangGraph Agent]
    AGENT -->|Tool Call| TOOLS[🔧 Tools]
    TOOLS -->|registrar_venta| DB[(Supabase)]
    TOOLS -->|consultar_inventario| DB
    AGENT -->|Respuesta| API
    API -->|WhatsApp API| WA
```

### Stack Tecnológico

| Capa | Tecnología | Justificación |
|---|---|---|
| **API** | FastAPI | Async, tipado, auto-docs |
| **Agente** | LangGraph + Gemini 2.0 Flash | ReAct pattern, tool calling nativo |
| **Base de Datos** | Supabase (PostgreSQL) | REST API, auth, RLS |
| **Mensajería** | WhatsApp Business Cloud API | Canal principal de bodegueros |
| **Observabilidad** | structlog (JSON) | Logs estructurados para producción |
| **Testing** | pytest + pytest-mock | 32 tests unitarios |
| **CI/CD** | GitHub Actions | Lint (ruff) + tests automáticos |
| **Gestión deps** | uv (Astral) | 10x más rápido que pip |

---

## 🚀 Quick Start

### Prerequisitos
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) instalado
- Cuenta de [Supabase](https://supabase.com)
- Cuenta de [Google AI Studio](https://aistudio.google.com) (API key de Gemini)

### 1. Clonar e instalar

```bash
git clone https://github.com/yourusername/quipu-ai.git
cd quipu-ai
uv sync
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
# Editar .env con tus credenciales
```

### 3. Ejecutar

```bash
# Server
uv run uvicorn main:app --port 8000 --reload

# Tests
uv run pytest tests/ -v
```

### 4. WhatsApp (opcional)

```bash
# Tunnel para exponer el server a Meta
ngrok http 8000

# Configurar la URL pública en Meta Developer > Webhook
```

---

## 📁 Estructura del Proyecto

```
quipu-ai/
├── app/
│   ├── agent/
│   │   ├── graph.py          # Grafo LangGraph (ReAct + retry)
│   │   └── state.py          # Estado del agente
│   ├── api/v1/
│   │   ├── chat.py            # POST /chat (test directo)
│   │   ├── clientes.py        # CRUD clientes
│   │   ├── health.py          # GET /health
│   │   ├── inventario.py      # CRUD inventario
│   │   ├── productos.py       # CRUD productos
│   │   ├── ventas.py          # CRUD ventas
│   │   └── webhook.py         # WhatsApp webhook (HMAC + historial)
│   ├── core/
│   │   ├── config.py          # Settings (Pydantic)
│   │   ├── database.py        # Supabase client
│   │   ├── exceptions.py      # Custom exceptions
│   │   └── logging.py         # structlog config
│   ├── repositories/          # Capa de datos (Supabase queries)
│   ├── services/              # Lógica de negocio
│   └── tools/                 # LangGraph tools (venta, inventario)
├── tests/unit/                # 32 tests
├── .github/workflows/ci.yml   # GitHub Actions
├── Dockerfile                 # Multi-stage (uv + slim)
├── main.py                    # App factory
└── pyproject.toml             # Dependencias (uv)
```

---

## 🔗 API Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/chat/` | Chat directo con el agente |
| `GET` | `/webhook/` | Verificación de Meta |
| `POST` | `/webhook/` | Recibir mensajes de WhatsApp |
| `POST` | `/api/v1/ventas/` | Registrar venta |
| `GET` | `/api/v1/ventas/` | Listar ventas |
| `POST` | `/api/v1/productos/` | Crear producto |
| `GET` | `/api/v1/productos/` | Listar productos |
| `GET` | `/api/v1/inventario/` | Listar inventario |
| `GET` | `/api/v1/clientes/` | Listar clientes |

📖 **Swagger UI**: `http://localhost:8000/docs`

---

## 🐳 Docker

```bash
# Build
docker build -t quipu-ai .

# Run
docker run -p 8000:8000 --env-file .env quipu-ai
```

---

## 🧪 Testing

```bash
# Todos los tests
uv run pytest tests/ -v

# Solo webhook tests
uv run pytest tests/unit/test_webhook.py -v

# Con coverage
uv run pytest tests/ --cov=app --cov-report=term-missing
```

---

## 📄 License

MIT
