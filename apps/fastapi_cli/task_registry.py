# task_registry.py
from worker import celery_app

TASKS = {}

def register_task(config):
    func = config["func"]
    name = config["name"]

    @celery_app.task(name=name)
    def task_wrapper(**kwargs):
        return func(**kwargs)

    TASKS[name] = task_wrapper