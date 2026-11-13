from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager

from src.shared.api.errors import AppError, app_error_handler, validation_exception_handler
from src.agents.fundamental.api.routes import router as fundamental_router
from src.agents.industry.api.routes import router as industry_router
from src.supervisor.api.routes import make_router as make_supervisor_router, make_technical_core_router
from src.agents.technical.api.routes import router as technical_router

from src.agents.flow.api.http import router as flow_router

supervisor_meaning_runtime = None

def install_supervisor_meaning_runtime(options):
    # Explicit options only; constructing a runtime does not read a provider key.
    from src.supervisor.application.meaning_gateway_factory import MeaningRuntime
    global supervisor_meaning_runtime
    supervisor_meaning_runtime = MeaningRuntime(options)


@asynccontextmanager
async def lifespan(app):
    import os
    from src.supervisor.application.meaning_gateway_factory import startup_options
    global supervisor_meaning_runtime
    supervisor_meaning_runtime = None
    options = startup_options(os.environ)
    if options is not None:
        install_supervisor_meaning_runtime(options)
    try:
        yield
    finally:
        supervisor_meaning_runtime = None
        if "app" in globals():app.state.technical_execution_runtime = None

supervisor_router = make_supervisor_router(runtime=lambda: supervisor_meaning_runtime)
supervisor_router.include_router(make_technical_core_router())

app = FastAPI(title="verith-ai", lifespan=lifespan)
app.state.technical_execution_runtime = None

def install_technical_execution_runtime(options):
    from src.agents.technical.application.execution_runtime import install_runtime
    app.state.technical_execution_runtime = install_runtime(options)


# 내부 AI endpoint 라우터와 §9 error envelope 핸들러 등록.
app.include_router(flow_router)
app.include_router(technical_router)
app.include_router(supervisor_router)
app.include_router(fundamental_router)
app.include_router(industry_router)
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai"}
