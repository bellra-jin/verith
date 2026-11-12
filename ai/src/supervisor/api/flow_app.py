"""Supervisor planning + Flow execution app without unrelated agent imports.

Run with ``uvicorn src.supervisor.api.flow_app:create_app --factory``.
The existing routers own all feature gates, authentication and deadlines.
This entry does not install a meaning-model runtime or configure providers.
"""
from fastapi import FastAPI


def create_app():
    from src.agents.flow.api.http import make_router as make_flow_router
    from src.supervisor.api.routes import make_router as make_supervisor_router

    app = FastAPI(title="verith-ai-supervisor-flow")
    app.include_router(make_flow_router())
    app.include_router(make_supervisor_router())

    @app.get('/health')
    def health():
        return {'status': 'ok', 'service': 'ai-supervisor-flow'}

    return app
