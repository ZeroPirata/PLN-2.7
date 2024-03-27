from fastapi import APIRouter
from .config import settings
from .responses import ResponseVersion, RequestHtml
from .processing import Processing

router = APIRouter()


@router.get(
    "/",
    description="Project version",
    response_description="Returns the name and the actual version of the project.",
    response_model=ResponseVersion,
    tags=["v1"],
)
def version():
    return {"version": settings.PROJECT_VERSION, "name": settings.PROJECT_NAME}


@router.post("/")
def processing(req: RequestHtml):
    return Processing(url=req.url, section=req.section, tag=req.tag).processing()
