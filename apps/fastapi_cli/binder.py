# binder.py
from registry import ROUTES
from config import config

def apply_config():
    for route in config.routes:
        name = route["name"]

        if name not in ROUTES:
            raise Exception(f"Function {name} not registered")

        # merge defaults
        merged = {**config.defaults, **route}

        ROUTES[name].update(merged)