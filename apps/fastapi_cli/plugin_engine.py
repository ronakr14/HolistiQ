# plugin_engine.py
from plugins.registry import get_plugin

def run_before_plugins(plugin_names, request, config, kwargs):
    for name in plugin_names:
        plugin = get_plugin(name)
        kwargs = plugin.before_request(request, config, kwargs)
    return kwargs

def run_after_plugins(plugin_names, request, response, config):
    for name in reversed(plugin_names):
        plugin = get_plugin(name)
        response = plugin.after_response(request, response, config)
    return response

def run_error_plugins(plugin_names, request, error, config):
    for name in plugin_names:
        plugin = get_plugin(name)
        plugin.on_error(request, error, config)