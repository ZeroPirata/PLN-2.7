from fastapi import FastAPI


class Settings:
    PROJECT_NAME: str = "PLN - Fatec - Atividade PP.2.7"
    PROJECT_VERSION: str = "1.0.0"


settings = Settings()


def include_router(app: FastAPI) -> None:
    from .routes import router

    app.include_router(router)


def start_application() -> FastAPI:
    app = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)
    include_router(app)
    return app
