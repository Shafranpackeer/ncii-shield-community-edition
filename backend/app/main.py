from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, discovery, confirmation, operations, config

app = FastAPI(title="NCII Shield API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(cases.router)
app.include_router(discovery.router)
app.include_router(confirmation.router)
app.include_router(operations.router)
app.include_router(config.router)


@app.get("/")
async def root():
    return {"message": "NCII Shield API v1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
