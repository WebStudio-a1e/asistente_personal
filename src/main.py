"""Punto de entrada de la aplicación — FastAPI base."""

from fastapi import FastAPI

app = FastAPI(title="asistente_personal", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok"}
