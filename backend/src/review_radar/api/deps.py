"""FastAPI dependencies. Routers ask for ports, never for concrete adapters."""

from typing import Annotated

from fastapi import Depends, Request

from review_radar.application.ports import ReadModel
from review_radar.application.releases import CompareReleases
from review_radar.application.replies import PostReply, ReviewReply
from review_radar.container import Container


def get_container(request: Request) -> Container:
    container: Container = request.app.state.container
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_read_model(container: ContainerDep) -> ReadModel:
    return container.read


def get_compare_releases(container: ContainerDep) -> CompareReleases:
    return container.compare_releases()


def get_review_reply(container: ContainerDep) -> ReviewReply:
    return container.review_reply()


def get_post_reply(container: ContainerDep) -> PostReply:
    return container.post_reply()


ReadModelDep = Annotated[ReadModel, Depends(get_read_model)]
CompareReleasesDep = Annotated[CompareReleases, Depends(get_compare_releases)]
ReviewReplyDep = Annotated[ReviewReply, Depends(get_review_reply)]
PostReplyDep = Annotated[PostReply, Depends(get_post_reply)]
