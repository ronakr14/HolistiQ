# cli2api

A lightweight execution platform to expose Python functions as:

* CLI commands
* REST APIs (FastAPI)
* Async jobs (Celery)
* Automation triggers (webhooks / n8n)

Built with a **config-driven + plugin-based architecture**, keeping business logic clean and infrastructure concerns isolated.

---

## 🧠 Core Philosophy

* **Functions = business logic (pure)**
* **YAML = control plane (behavior)**
* **Plugins = execution features (auth, rate limit, etc.)**

> One function → multiple execution surfaces

---

## ⚙️ Features

* FastAPI auto route generation
* Typer-based CLI exposure
* Celery async job execution
* Redis-backed:

  * Rate limiting
  * Idempotency keys
* YAML-based configuration
* Plugin system (extensible middleware)
* Observability-ready (logging, metrics, tracing)

---

## 📦 Architecture Overview

```
Function
   ↓
Decorator (@expose)
   ↓
Registry
   ↓
YAML Config Binding
   ↓
Execution Layer
   ├── CLI (Typer)
   ├── API (FastAPI)
   └── Worker (Celery)
         ↓
      Redis
         ↓
    Plugins (Auth, RateLimit, Idempotency, Logging)
```

---

## 📁 Project Structure

```
cli2api/
│── decorators.py
│── registry.py
│── app.py
│── worker.py
│── cli.py
│── config.py
│── binder.py
│── plugin_engine.py
│── redis_client.py
│── idempotency.py
│
├── plugins/
│   ├── base.py
│   ├── registry.py
│   ├── logging.py
│   ├── rate_limit.py
│   ├── idempotency.py
│
├── config.yaml
```

---

## 🧩 YAML Configuration

```yaml
app:
  name: cli2api-app

defaults:
  auth: true
  rate_limit: 10
  async_task: false
  idempotency: true

plugins:
  - logging
  - rate_limit
  - idempotency

routes:
  - name: process_data
    path: /process
    method: POST
    async_task: true
    rate_limit: 5
    plugins: [rate_limit, idempotency]

  - name: health
    path: /health
    method: GET
    auth: false
    plugins: [logging]
```

---

## 🔌 Plugin System

### Supported Hooks

* `before_request` → input validation / mutation
* `after_response` → response transformation
* `on_error` → error handling
* `on_startup` → initialization

---

## 🔐 Idempotency

* Uses `Idempotency-Key` header
* Redis-backed storage
* Prevents duplicate execution

---

## 🚦 Rate Limiting

* Per IP + route
* Redis atomic counters
* Configurable via YAML

---

## ⚡ Async Jobs

* Powered by Celery
* Redis as broker + backend
* Returns `task_id` for tracking

---

## 📊 Observability

* Structured logging
* Ready for:

  * Prometheus (metrics)
  * Grafana (dashboards)
  * OpenTelemetry (tracing)

---

## ▶️ Running the System

### Start Redis

```
redis-server
```

### Start API

```
uvicorn main:app --reload
```

### Start Worker

```
celery -A worker.celery_app worker --loglevel=info
```

---

## ⚠️ Design Constraints

* Keep functions pure (no infra logic)
* Avoid overloading YAML with logic
* Keep plugin list minimal and predictable
* Order of plugins matters

---

## 🚀 Roadmap

* Plugin config support
* Plugin dependency system
* Distributed tracing
* Config hot reload
* Pip-installable plugin ecosystem

---

## 🧭 Positioning

This is not just a FastAPI wrapper.

It’s a **lightweight internal execution platform** for:

* automation
* internal tools
* developer workflows

Use it like one.
