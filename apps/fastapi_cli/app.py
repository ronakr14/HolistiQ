# app.py
from fastapi import FastAPI
from registry import ROUTES
import inspect

app = FastAPI(title="CLI to API Adapter")

def create_endpoint(func):
    async def endpoint(**kwargs):
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)
    return endpoint

def register_routes(app: FastAPI):
    for path, func in ROUTES.items():
        endpoint = create_endpoint(func)

        app.add_api_route(
            path,
            endpoint,
            methods=["GET", "POST"],
            name=func.__name__,
        )

register_routes(app)



# app.py
from fastapi import FastAPI, Request, HTTPException, Depends
from registry import ROUTES
import inspect
import time

app = FastAPI()

# In-memory stores (replace later with Redis)
RATE_LIMIT_STORE = {}
API_KEYS = {"secret123"}  # move to env/db

# ---- AUTH ----
def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API Key")

# ---- RATE LIMIT ----
def check_rate_limit(path: str, limit: int, request: Request):
    client = request.client.host
    key = f"{client}:{path}"
    now = time.time()

    window = 60
    requests = RATE_LIMIT_STORE.get(key, [])

    # remove old requests
    requests = [r for r in requests if now - r < window]

    if len(requests) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    requests.append(now)
    RATE_LIMIT_STORE[key] = requests

# ---- ENDPOINT FACTORY ----
def create_endpoint(func, config):
    async def endpoint(request: Request, **kwargs):
        # Auth
        if config["auth"]:
            verify_api_key(request)

        # Rate limit
        check_rate_limit(request.url.path, config["rate_limit"], request)

        # Logging
        print(f"[LOG] {request.method} {request.url.path} | params={kwargs}")

        # Execution
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)

    return endpoint

# ---- REGISTER ROUTES ----
def register_routes(app: FastAPI):
    for path, config in ROUTES.items():
        endpoint = create_endpoint(config["func"], config)

        app.add_api_route(
            path,
            endpoint,
            methods=[config["method"]],
            name=config["func"].__name__,
        )

register_routes(app)



# app.py
from fastapi import FastAPI, Request
from registry import ROUTES
from task_registry import TASKS

app = FastAPI()

def create_endpoint(config):
    func = config["func"]

    async def endpoint(request: Request, **kwargs):
        # rate limit
        check_rate_limit(config["path"], config["rate_limit"], request.client.host)

        # async execution
        if config["async_task"]:
            task = TASKS[config["name"]].delay(**kwargs)
            return {"task_id": task.id, "status": "queued"}

        return func(**kwargs)

    return endpoint


# app.py (inside endpoint)
from fastapi import Request, HTTPException
from idempotency import get_key, set_processing, set_completed

async def endpoint(request: Request, **kwargs):
    idem_key = request.headers.get("Idempotency-Key")

    if idem_key:
        existing = get_key(idem_key)

        if existing:
            if existing["status"] == "completed":
                return existing["response"]
            raise HTTPException(409, "Request already processing")

        set_processing(idem_key)

    # ---- EXECUTION ----
    if config["async_task"]:
        task = TASKS[config["name"]].delay(**kwargs)
        response = {"task_id": task.id}
    else:
        response = func(**kwargs)

    if idem_key:
        set_completed(idem_key, response)

    return response


# app.py
from fastapi import FastAPI
from registry import ROUTES
from binder import apply_config

def create_app():
    app = FastAPI()

    apply_config()  # apply YAML

    for name, config in ROUTES.items():
        func = config["func"]

        endpoint = create_endpoint(config)

        app.add_api_route(
            config["path"],
            endpoint,
            methods=[config["method"]],
            name=name,
        )

    return app


if config.get("idempotency"):
    handle_idempotency()

if config.get("async_task"):
    queue_task()


    def create_endpoint(config):
    func = config["func"]
    plugins = config.get("plugins", [])

    async def endpoint(request: Request, **kwargs):
        try:
            # BEFORE
            kwargs = run_before_plugins(plugins, request, config, kwargs)

            # EXECUTION
            if config.get("async_task"):
                task = TASKS[config["name"]].delay(**kwargs)
                response = {"task_id": task.id}
            else:
                response = func(**kwargs)

            # AFTER
            response = run_after_plugins(plugins, request, response, config)

            return response

        except CachedResponse as e:
            return e.response

        except Exception as e:
            run_error_plugins(plugins, request, e, config)
            raise e

    return endpoint