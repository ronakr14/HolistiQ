# plugins/registry.py
PLUGINS = {}

def register_plugin(name: str, plugin):
    PLUGINS[name] = plugin

def get_plugin(name: str):
    if name not in PLUGINS:
        raise Exception(f"Plugin {name} not found")
    return PLUGINS[name]