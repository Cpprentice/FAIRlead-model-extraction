from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from fairlead_core.settings import Settings


def on_app_created(app: FastAPI):
    settings = Settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount('/semantics/ontology/docs', StaticFiles(directory='simpler-api/static/ontology-docs', html=True), name='onto-docs')
    app.mount('/semantics/static', StaticFiles(directory='simpler-api/static/raw'), name='raw-files')
