from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import example, feature_flow, flow_generation
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Boilerplate FastAPI App")

# Create Database Tables on Startup
from orm_model.core_models import Base, engine
Base.metadata.create_all(bind=engine)

# CORS Configuration
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(example.router, prefix="/api", tags=["Example"])
app.include_router(flow_generation.router, prefix="/api")
app.include_router(feature_flow.router, prefix="/api")


@app.get("/")
def home():
    return {"message": "Welcome to the Boilerplate FastAPI Application"}

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
