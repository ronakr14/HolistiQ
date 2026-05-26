# registry.py
from typing import Callable, Dict

ROUTES: Dict[str, Callable] = {}

def register_route(path: str, func: Callable):
    ROUTES[path] = func


# registry.py
ROUTES = {}

def register_route(path: str, config: dict):
    ROUTES[path] = config


# registry.py
ROUTES = {}

def register_route(config):
    ROUTES[config["name"]] = config