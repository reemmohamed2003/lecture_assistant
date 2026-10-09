from fastapi import FastAPI

from m4.api import router

app = FastAPI(title="EduPilot M4")
app.include_router(router)