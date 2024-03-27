from pydantic import BaseModel


class ResponseVersion(BaseModel):
    version: str
    name: str


class RequestHtml(BaseModel):
    url: str
    section: str
    tag: str
