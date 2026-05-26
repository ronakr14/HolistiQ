# cli.py
from decorators import expose_api

@expose_api("/add")
def add(a: int, b: int):
    return {"result": a + b}

@expose_api("/hello")
def hello(name: str = "world"):
    return {"message": f"Hello {name}"}


# cli.py
from decorators import expose_api
from pydantic import BaseModel

class AddInput(BaseModel):
    a: int
    b: int

@expose_api(rate_limit=5)
def add(a: int, b: int):
    return {"result": a + b}

@expose_api(auth=False)
def health():
    return {"status": "ok"}