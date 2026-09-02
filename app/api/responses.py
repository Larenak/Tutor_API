from pydantic import BaseModel


class SuccessResponse[DataT](BaseModel):
    success: bool = True
    data: DataT
    meta: dict[str, object] = {}


def success[DataT](
    data: DataT,
    meta: dict[str, object] | None = None,
) -> SuccessResponse[DataT]:
    return SuccessResponse(data=data, meta=meta or {})
