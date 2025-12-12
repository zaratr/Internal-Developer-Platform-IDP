import contextvars

request_id_ctx = contextvars.ContextVar("request_id", default="-")


def set_request_id(value: str) -> None:
    request_id_ctx.set(value)


def get_request_id() -> str:
    return request_id_ctx.get()
