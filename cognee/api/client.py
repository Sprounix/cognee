"""FastAPI server for the Cognee API."""

import os
import uuid
import socket
import time
import json
import uvicorn
import sentry_sdk
from traceback import format_exc
from contextlib import asynccontextmanager
from fastapi import Request
from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi

from cognee.exceptions import CogneeApiError
from cognee.shared.logging_utils import get_logger, setup_logging, structlog
from cognee.api.v1.permissions.routers import get_permissions_router
from cognee.api.v1.settings.routers import get_settings_router
from cognee.api.v1.datasets.routers import get_datasets_router
from cognee.api.v1.cognify.routers import get_code_pipeline_router, get_cognify_router
from cognee.api.v1.search.routers import get_search_router
from cognee.api.v1.recall.routers import get_recall_router
from cognee.api.v1.job.routers import get_job_router
from cognee.api.v1.add.routers import get_add_router
from cognee.api.v1.delete.routers import get_delete_router
from cognee.api.v1.responses.routers import get_responses_router
from cognee.api.v1.users.routers import (
    get_auth_router,
    get_register_router,
    get_reset_password_router,
    get_verify_router,
    get_users_router,
    get_visualize_router,
)

logger = get_logger()

if os.getenv("ENV", "prod") == "prod":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_REPORTING_URL"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )


app_environment = os.getenv("ENV", "prod")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # from cognee.modules.data.deletion import prune_system, prune_data
    # await prune_data()
    # await prune_system(metadata = True)
    # if app_environment == "local" or app_environment == "dev":
    from cognee.infrastructure.databases.relational import get_relational_engine

    db_engine = get_relational_engine()
    await db_engine.create_database()

    from cognee.modules.users.methods import get_default_user

    await get_default_user()

    yield


app = FastAPI(debug=app_environment != "prod", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["OPTIONS", "GET", "POST", "DELETE"],
    allow_headers=["*"],
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Cognee API",
        version="1.0.0",
        description="Cognee API with Bearer token and Cookie auth",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {"type": "http", "scheme": "bearer"},
        "CookieAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": os.getenv("AUTH_TOKEN_COOKIE_NAME", "auth_token"),
        },
    }

    openapi_schema["security"] = [{"BearerAuth": []}, {"CookieAuth": []}]

    app.openapi_schema = openapi_schema

    return app.openapi_schema


app.openapi = custom_openapi


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/api/v1/auth/login":
        return JSONResponse(
            status_code=400,
            content={"detail": "LOGIN_BAD_CREDENTIALS"},
        )

    return JSONResponse(
        status_code=400,
        content=jsonable_encoder({"detail": exc.errors(), "body": exc.body}),
    )


@app.exception_handler(CogneeApiError)
async def exception_handler(_: Request, exc: CogneeApiError) -> JSONResponse:
    detail = {}

    if exc.name and exc.message and exc.status_code:
        status_code = exc.status_code
        detail["message"] = f"{exc.message} [{exc.name}]"
    else:
        # Log an error indicating the exception is improperly defined
        logger.error("Improperly defined exception: %s", exc)
        # Provide a default error response
        detail["message"] = "An unexpected error occurred."
        status_code = status.HTTP_418_IM_A_TEAPOT

    # log the stack trace for easier serverside debugging
    logger.error(format_exc())
    return JSONResponse(status_code=status_code, content={"detail": detail["message"]})


def get_real_ip(request: Request) -> str:
    """获取客户端真实IP地址"""
    # 可信代理IP列表（根据你的部署环境配置）
    trusted_proxies = {"127.0.0.1", "::1"}  # 本地代理

    # 获取直接连接的客户端IP
    client_ip = request.client.host if request.client else None

    # 检查头部
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # X-Forwarded-For 格式: client, proxy1, proxy2
        proxies = [ip.strip() for ip in x_forwarded_for.split(",")]
        # 从右向左找到第一个不可信代理
        for ip in reversed(proxies):
            if ip not in trusted_proxies:
                client_ip = ip
                break

    # 检查其他头部
    if not client_ip:
        client_ip = (
            request.headers.get("cf-connecting-ip") or  # Cloudflare
            request.headers.get("x-real-ip") or
            request.client.host
        )

    return client_ip


@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = dict(request.headers).get("traceId") or uuid.uuid4().hex
    structlog.contextvars.bind_contextvars(trace_id=trace_id)

    headers = dict(request.headers)
    start_time = time.time()
    server_name = socket.gethostname()
    content_type = headers.get('content-type')
    req_body_json = None
    try:
        if 'application/json' in content_type:
            req_body_json = await request.json()
        elif 'application/x-www-form-urlencoded' in content_type:
            form_data = await request.form()
            req_body_json = dict(form_data)
    except:
        pass

    response = await call_next(request)

    # pop掉log中不想输出的key
    for k in ["authorization"]:
        headers.pop(k, None)

    params = dict(
        server_name=server_name, url=str(request.url), method=request.method, headers=headers,
        req_body_args=req_body_json, status_code=response.status_code, res_body=None, client_ip=get_real_ip(request),
    )

    response_body = b""
    async for chunk in response.body_iterator:
        response_body += chunk

    response_body_str = response_body.decode()

    try:
        response_json = json.loads(response_body_str)
    except json.JSONDecodeError:
        response_json = None

    process_time = time.time() - start_time
    params["res_time"] = round(process_time, 4)
    params["res_body"] = response_json

    logger.info("log_requests", params)

    return Response(
        content=response_body_str,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type
    )


@app.get("/")
async def root():
    """
    Root endpoint that returns a welcome message.
    """
    return {"message": "Hello, World, I am alive!"}


@app.get("/health")
def health_check():
    """
    Health check endpoint that returns the server status.
    """
    return Response(status_code=200)


app.include_router(get_auth_router(), prefix="/api/v1/auth", tags=["auth"])

app.include_router(
    get_register_router(),
    prefix="/api/v1/auth",
    tags=["auth"],
)

app.include_router(
    get_reset_password_router(),
    prefix="/api/v1/auth",
    tags=["auth"],
)

app.include_router(
    get_verify_router(),
    prefix="/api/v1/auth",
    tags=["auth"],
)

app.include_router(get_add_router(), prefix="/api/v1/add", tags=["add"])

app.include_router(get_cognify_router(), prefix="/api/v1/cognify", tags=["cognify"])

app.include_router(get_search_router(), prefix="/api/v1/search", tags=["search"])

app.include_router(get_recall_router(), prefix="/api/v1/recommend", tags=["recommend"])

app.include_router(get_job_router(), prefix="/api/v1/job", tags=["job"])

app.include_router(
    get_permissions_router(),
    prefix="/api/v1/permissions",
    tags=["permissions"],
)

app.include_router(get_datasets_router(), prefix="/api/v1/datasets", tags=["datasets"])

app.include_router(get_settings_router(), prefix="/api/v1/settings", tags=["settings"])

app.include_router(get_visualize_router(), prefix="/api/v1/visualize", tags=["visualize"])

app.include_router(get_delete_router(), prefix="/api/v1/delete", tags=["delete"])

app.include_router(get_responses_router(), prefix="/api/v1/responses", tags=["responses"])

codegraph_routes = get_code_pipeline_router()
if codegraph_routes:
    app.include_router(codegraph_routes, prefix="/api/v1/code-pipeline", tags=["code-pipeline"])

app.include_router(
    get_users_router(),
    prefix="/api/v1/users",
    tags=["users"],
)


def start_api_server(host: str = "0.0.0.0", port: int = 9876):
    """
    Start the API server using uvicorn.
    Parameters:
    host (str): The host for the server.
    port (int): The port for the server.
    """
    try:
        logger.info("Starting server at %s:%s", host, port)

        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.exception(f"Failed to start server: {e}")
        # Here you could add any cleanup code or error recovery code.
        raise e


if __name__ == "__main__":
    logger = setup_logging()

    start_api_server(
        host=os.getenv("HTTP_API_HOST", "0.0.0.0"), port=int(os.getenv("HTTP_API_PORT", 9876))
    )
