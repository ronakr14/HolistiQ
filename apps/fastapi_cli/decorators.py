# decorators.py
from registry import register_route

def expose_api(path: str):
    def decorator(func):
        register_route(path, func)
        return func
    return decorator


# decorators.py
from registry import register_route

def expose_api(
    path: str = None,
    method: str = "POST",
    auth: bool = True,
    rate_limit: int = 10,  # requests per minute
):
    def decorator(func):
        route_path = path or f"/{func.__name__.replace('_', '-')}"
        
        register_route(route_path, {
            "func": func,
            "method": method,
            "auth": auth,
            "rate_limit": rate_limit,
        })
        return func
    return decorator


# decorators.py
from registry import register_route, register_task, register_cli

def expose(
    path: str = None,
    method: str = "POST",
    auth: bool = True,
    rate_limit: int = 10,
    async_task: bool = False,
):
    def decorator(func):
        name = func.__name__
        route_path = path or f"/{name.replace('_', '-')}"
        
        config = {
            "name": name,
            "func": func,
            "path": route_path,
            "method": method,
            "auth": auth,
            "rate_limit": rate_limit,
            "async_task": async_task,
        }

        register_route(config)
        register_cli(config)

        if async_task:
            register_task(config)

        return func
    return decorator



# decorators.py
from registry import register_route

def expose(func):
    register_route({
        "name": func.__name__,
        "func": func,
    })
    return func