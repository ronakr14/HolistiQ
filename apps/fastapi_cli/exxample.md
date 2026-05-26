# example.md

## 🧪 Basic Example

### 1. Define Function

```python
from cli2api import expose

@expose
def add(a: int, b: int):
    return {"result": a + b}
```

---

### 2. YAML Config

```yaml
routes:
  - name: add
    path: /add
    method: POST
    plugins: [logging]
```

---

### 3. Run API

```
uvicorn main:app
```

Test:

```
POST /add?a=1&b=2
```

---

## ⚡ Async Example

```python
@expose
def process_data(x: int, y: int):
    return x * y
```

```yaml
routes:
  - name: process_data
    path: /process
    async_task: true
    plugins: [rate_limit]
```

### API Call

```
POST /process?x=2&y=3
```

Response:

```json
{
  "task_id": "abc123"
}
```

---

## 🔍 Check Task Status

```
GET /tasks/{task_id}
```

---

## 🔐 Idempotency Example

### Request

```
POST /process
Idempotency-Key: xyz-123
```

### Behavior

* First call → executes
* Second call → returns cached response

---

## 🖥️ CLI Usage

```
cli2api add --a 1 --b 2
```

Same function, no duplication.

---

## 🔌 Plugin Example

### Enable Plugins

```yaml
plugins:
  - logging
  - rate_limit
  - idempotency
```

### Per Route

```yaml
routes:
  - name: process_data
    plugins: [rate_limit, idempotency]
```

---

## 🌐 Automation (n8n / Webhook)

Use API endpoints as triggers:

```
POST /process
```

Flow:

* Trigger → API
* API → Celery job
* Return task_id
* Continue workflow

---

## 🧠 Advanced Example

```python
@expose
def generate_report(user_id: int):
    return {"report": f"Report for {user_id}"}
```

```yaml
routes:
  - name: generate_report
    path: /report
    async_task: true
    rate_limit: 3
    plugins: [auth, rate_limit, idempotency]
```

---

## ⚠️ Gotchas

* Plugin order matters
* YAML name must match function name
* Idempotency requires client-provided key
* Async jobs need worker running

---

## 🚀 Real Use Cases

* Internal automation APIs
* Data pipelines triggers
* CLI tools → APIs instantly
* n8n / webhook workflows
* Background processing systems

---

## 🧭 Summary

Write function once:

```python
@expose
def do_work():
    pass
```

Get for free:

* CLI command
* API endpoint
* Async job
* Automation trigger
* Observability hooks

That’s the leverage.
