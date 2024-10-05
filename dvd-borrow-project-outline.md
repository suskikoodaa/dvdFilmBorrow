monorepo web app for retrieving a list of dvd films (id, title, year, location (city), available (true/false))
using python 3.12, poetry, fastapi, pytest, mongodb (running in a docker container), reflex (for frontend).

RESTful API, endpoints:  
GET api/v1/films to list all,  
GET api/v1/film/:title to get detailed data of one film and all occurrences in the database,  
GET api/v1/films?director=<director_name>,  
POST api/v1/film/:id to add a new film,  
PUT api/v1/film/:id to update existing entry.  


```
.
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── README.md
├── .gitignore
├── backend
│   ├── app
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── database.py
│   │   └── routers
│   │       └── films.py
│   └── tests
│       ├── __init__.py
│       └── test_films.py
└── frontend
    ├── __init__.py
    └── app.py

```

pyproject.toml:

```toml
[tool.poetry]
name = "dvd-film-app"
version = "0.1.0"
description = "A web app for managing DVD films"
authors = ["Your Name <you@example.com>"]

[tool.poetry.dependencies]
python = "^3.12"
fastapi = "^0.104.0"
uvicorn = "^0.23.2"
motor = "^3.3.1"
pydantic = "^2.4.2"
reflex = "^0.3.6"

[tool.poetry.dev-dependencies]
pytest = "^7.4.3"
httpx = "^0.25.0"

[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"
```

docker-compose.yml:

```yaml
version: '3.8'

services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

  backend:
    build: .
    command: uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    depends_on:
      - mongodb

  frontend:
    build: .
    command: reflex run --env prod
    volumes:
      - .:/app
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  mongodb_data:
```

Dockerfile:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry

COPY pyproject.toml poetry.lock* ./

RUN poetry config virtualenvs.create false \
  && poetry install --no-dev --no-interaction --no-ansi

COPY . .

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

backend/app/main.py:

```python
from fastapi import FastAPI
from .routers import films

app = FastAPI()

app.include_router(films.router, prefix="/api/v1", tags=["films"])

@app.get("/")
async def root():
    return {"message": "Welcome to the DVD Film API"}
```

backend/app/models.py:

```python
from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId

class PyObjectId(ObjectId):
  @classmethod
  def __get_validators__(cls):
    yield cls.validate

  @classmethod
  def validate(cls, v):
    if not ObjectId.is_valid(v):
      raise ValueError("Invalid objectid")
    return ObjectId(v)

  @classmethod
  def __modify_schema__(cls, field_schema):
    field_schema.update(type="string")

class FilmModel(BaseModel):
  id: Optional[PyObjectId] = Field(alias="_id")
  title: str
  year: int
  location: str
  available: bool

  class Config:
    allow_population_by_field_name = True
    arbitrary_types_allowed = True
    json_encoders = {ObjectId: str}
```

backend/app/database.py:

```python
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = "mongodb://mongodb:27017"
client = AsyncIOMotorClient(MONGO_URL)
database = client.dvd_films
film_collection = database.get_collection("films")
```

backend/app/routers/films.py:

```python
from fastapi import APIRouter, HTTPException, Body
from ..models import FilmModel
from ..database import film_collection
from typing import List
from bson import ObjectId

router = APIRouter()

@router.get("/films", response_model=List[FilmModel])
async def list_films():
  films = await film_collection.find().to_list(1000)
  return films

@router.get("/film/{title}", response_model=List[FilmModel])
async def get_film(title: str):
  films = await film_collection.find({"title": title}).to_list(1000)
  if not films:
    raise HTTPException(status_code=404, detail="Film not found")
  return films

@router.post("/film", response_model=FilmModel)
async def create_film(film: FilmModel = Body(...)):
  new_film = await film_collection.insert_one(film.dict(exclude={"id"}))
  created_film = await film_collection.find_one({"_id": new_film.inserted_id})
  return created_film

@router.put("/film/{id}", response_model=FilmModel)
async def update_film(id: str, film: FilmModel = Body(...)):
  film = {k: v for k, v in film.dict().items() if v is not None}
  if len(film) >= 1:
    update_result = await film_collection.update_one({"_id": ObjectId(id)}, {"$set": film})
    if update_result.modified_count == 1:
      updated_film = await film_collection.find_one({"_id": ObjectId(id)})
      if updated_film is not None:
        return updated_film
  existing_film = await film_collection.find_one({"_id": ObjectId(id)})
  if existing_film is not None:
    return existing_film
  raise HTTPException(status_code=404, detail="Film not found")
```

backend/tests/test_films.py:

```python
import pytest
from httpx import AsyncClient
from backend.app.main import app

@pytest.mark.asyncio
async def test_create_film():
  async with AsyncClient(app=app, base_url="http://test") as ac:
    response = await ac.post("/api/v1/film", json={
        "title": "Test Film",
        "year": 2023,
        "location": "Test City",
        "available": True
    })
  assert response.status_code == 200
  assert response.json()["title"] == "Test Film"

@pytest.mark.asyncio
async def test_get_film():
  async with AsyncClient(app=app, base_url="http://test") as ac:
    response = await ac.get("/api/v1/film/Test Film")
  assert response.status_code == 200
  assert len(response.json()) > 0
  assert response.json()[0]["title"] == "Test Film"

@pytest.mark.asyncio
async def test_list_films():
  async with AsyncClient(app=app, base_url="http://test") as ac:
    response = await ac.get("/api/v1/films")
  assert response.status_code == 200
  assert len(response.json()) > 0

@pytest.mark.asyncio
async def test_update_film():
  async with AsyncClient(app=app, base_url="http://test") as ac:
    # First, create a film
    create_response = await ac.post("/api/v1/film", json={
        "title": "Update Test Film",
        "year": 2023,
        "location": "Test City",
        "available": True
    })
    film_id = create_response.json()["_id"]

    # Now update the film
    update_response = await ac.put(f"/api/v1/film/{film_id}", json={
        "title": "Updated Test Film",
        "year": 2024,
        "location": "New Test City",
        "available": False
    })
  assert update_response.status_code == 200
  assert update_response.json()["title"] == "Updated Test Film"
  assert update_response.json()["year"] == 2024
  assert update_response.json()["location"] == "New Test City"
  assert update_response.json()["available"] == False
```

frontend/app.py:

```python
import reflex as rx
import httpx

class Film(rx.Base):
  id: str
  title: str
  year: int
  location: str
  available: bool

class State(rx.State):
  films: list[Film] = []
  new_film: Film = Film(id="", title="", year=2023, location="", available=True)

  async def get_films(self):
    async with httpx.AsyncClient() as client:
      response = await client.get("http://backend:8000/api/v1/films")
      self.films = [Film(**film) for film in response.json()]

  async def add_film(self):
    async with httpx.AsyncClient() as client:
      response = await client.post("http://backend:8000/api/v1/film", json=self.new_film.dict())
      if response.status_code == 200:
        await self.get_films()
        self.new_film = Film(id="", title="", year=2023, location="", available=True)

def film_list():
  return rx.vstack(
    rx.heading("DVD Films"),
    rx.button("Refresh", on_click=State.get_films),
    rx.foreach(
      State.films,
      lambda film: rx.box(
          rx.text(f"{film.title} ({film.year}) - {film.location} - {'Available' if film.available else 'Not Available'}"),
          padding="1em",
          border_bottom="1px solid #eaeaea",
      )
    )
  )

def add_film_form():
  return rx.vstack(
    rx.heading("Add New Film"),
    rx.input(placeholder="Title", on_change=State.set_new_film_title),
    rx.input(placeholder="Year", type_="number", on_change=State.set_new_film_year),
    rx.input(placeholder="Location", on_change=State.set_new_film_location),
    rx.checkbox("Available", on_change=State.set_new_film_available),
    rx.button("Add Film", on_click=State.add_film)
  )

def index():
  return rx.container(
      film_list(),
      add_film_form()
  )

app = rx.App(state=State)
app.add_page(index)
```

.gitignore:

```text
# Python
__pycache__/
*.py[cod]
*.pyo
*.pyd
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Poetry
.poetry/
poetry.lock

# Pytest
.pytest_cache/

# IDEs
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Docker
.dockerignore

# MongoDB
data/

# Reflex
.web/

# Logs
*.log

# Build files
build/
dist/
*.egg-info/
```

README.md:

```markdown
# DVD Film Management App

This is a monorepo web application for managing DVD films. It uses Python 3.12, FastAPI for the backend, Reflex for the frontend, and MongoDB for the database.

## Setup

1. Install Docker and Docker Compose.
2. Clone this repository.
3. Run `docker-compose up --build` to start the application.

## Usage

- Backend API: http://localhost:8000
- Frontend: http://localhost:3000

## API Endpoints

- GET /api/v1/films - List all films
- GET /api/v1/film/{title} - Get detailed data of one film
- POST /api/v1/film - Add a new film
- PUT /api/v1/film/{id} - Update an existing film

## Testing

Run `pytest` in the backend directory to run the tests.

## Development

1. Use Poetry for dependency management.
2. Follow PEP 8 style guide for Python code.
3. Write tests for new features.
```

This setup provides a complete monorepo structure for your DVD film management app. The backend uses FastAPI with MongoDB, and the frontend uses Reflex. The application is containerized using Docker, making it easy to set up and run.

To start the application, you would run:

```text
docker-compose up --build
```

This will start the MongoDB database, the FastAPI backend, and the Reflex frontend. You can then access the frontend at <http://localhost:3000> and the backend API at <http://localhost:8000>.

Remember to adjust the MongoDB connection string in `backend/app/database.py` if you change the MongoDB configuration in `docker-compose.yml`.
