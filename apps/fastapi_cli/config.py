# config.py
import yaml

class Config:
    def __init__(self, path="config.yaml"):
        with open(path, "r") as f:
            self.raw = yaml.safe_load(f)

        self.defaults = self.raw.get("defaults", {})
        self.routes = self.raw.get("routes", [])

config = Config()