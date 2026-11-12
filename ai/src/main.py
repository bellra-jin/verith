from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.shared.api.errors import AppError, app_error_handler, validation_exception_handler
from src.agents.fundamental.api.routes import router as fundamental_router
from src.agents.industry.api.routes import router as industry_router
from src.supervisor.api.routes import make_router as make_supervisor_router
from src.agents.technical.api.routes import router as technical_router

from src.agents.flow.api.http import router as flow_router

supervisor_meaning_runtime = None

def install_supervisor_meaning_runtime(options):
    # Called explicitly by a deployment composition, never from environment/import.
    from src.supervisor.application.meaning_gateway_factory import MeaningRuntime
    global supervisor_meaning_runtime
    supervisor_meaning_runtime = MeaningRuntime(options)

supervisor_router = make_supervisor_router(runtime=lambda: supervisor_meaning_runtime)

app = FastAPI(title="verith-ai")

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
