from fastapi import FastAPI

from app.api.router import router

app = FastAPI(title="Payment Processing Service")
app.include_router(router)
