from .config import start_application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app: FastAPI = start_application()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
