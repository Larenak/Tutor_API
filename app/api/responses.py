from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    success: bool = True
    data: DataT
    meta: dict[str, object] = {}


def success(data: DataT, meta: dict[str, object] | None = None) -> SuccessResponse[DataT]:
    return SuccessResponse(data=data, meta=meta or {})
