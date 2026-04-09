from fastapi import FastAPI

from app.routers import agents, auth, tasks, traces

app = FastAPI(title="Managed Agents API", version="0.1.0")


@app.get("/healthz", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(agents.router, prefix="/v1")
app.include_router(tasks.router, prefix="/v1")
app.include_router(auth.router, prefix="/v1")
app.include_router(traces.router, prefix="/v1")
