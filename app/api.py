from fastapi import FastAPI

from app.routes import main_router

app = FastAPI(
    title="SupplyService",
    debug=True,
)

app.include_router(main_router)
