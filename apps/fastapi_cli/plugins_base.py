# plugins/base.py
class Plugin:
    def before_request(self, request, config, kwargs):
        return kwargs

    def after_response(self, request, response, config):
        return response

    def on_error(self, request, error, config):
        raise error

    def on_startup(self, app):
        pass