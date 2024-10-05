from fastapi import FastAPI
#from .routers import films

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Welcome to the DVD Film API"}


@app.get("/greet/{name}")
async def greet(name):
    return {"message": f"Moi, {name}!"}
#Lisättiin api end point, joka tervehtii käyttäjää
#Tee end point, joka ottaa vastaan kaksi numeroa ja palauttaa niiden summan


@app.get("/add/{number1}/{number2}")
async def add_numbers(number1: int, number2: int):
    return {"message": f"{number1=} + {number2=} = {number1 + number2}"}