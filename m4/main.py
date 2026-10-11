from fastapi import FastAPI

from m4.api import router

app = FastAPI(title="Rafeeq")
app.include_router(router)