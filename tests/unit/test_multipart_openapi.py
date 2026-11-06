from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI

from app.main import create_app

pytestmark = pytest.mark.unit

_MULTIPART_OPERATIONS = {
    ("/api/accounts/import", "post"),
    ("/backend-api/transcribe", "post"),
    ("/v1/audio/transcriptions", "post"),
    ("/v1/images/edits", "post"),
}


def _nullable_string(title: str) -> dict[str, Any]:
    return {
        "anyOf": [{"type": "string"}, {"type": "null"}],
        "title": title,
    }


def _binary(title: str) -> dict[str, Any]:
    return {
        "type": "string",
        "contentMediaType": "application/octet-stream",
        "title": title,
    }


def _binary_array(title: str) -> dict[str, Any]:
    return {
        "anyOf": [
            {
                "type": "array",
                "items": {
                    "type": "string",
                    "contentMediaType": "application/octet-stream",
                },
            },
            {"type": "null"},
        ],
        "title": title,
    }


def _request_schema(openapi: dict[str, Any], path: str) -> dict[str, Any]:
    request_body = openapi["paths"][path]["post"]["requestBody"]
    assert set(request_body) == {"content", "required"}
    assert request_body["required"] is True
    assert set(request_body["content"]) == {"multipart/form-data"}
    schema = request_body["content"]["multipart/form-data"]["schema"]
    if "$ref" not in schema:
        return schema
    component_name = schema["$ref"].rsplit("/", 1)[-1]
    return openapi["components"]["schemas"][component_name]


def mount_legacy_upload_probe(app: FastAPI) -> None:
    """Keep generic ingress/schema coverage without re-enabling retired routes in production."""
    from app.modules.accounts.api import router as accounts_router
    from app.modules.proxy.api import files_router, transcribe_router, v1_router

    original = list(app.router.routes)
    for router in (accounts_router, v1_router, transcribe_router, files_router):
        app.include_router(router)
    paths = {path for path, _ in _MULTIPART_OPERATIONS} | {"/backend-api/files"}
    probes = [route for route in app.router.routes[len(original) :] if getattr(route, "path", None) in paths]
    app.router.routes[:] = probes + original
    app.openapi_schema = None


def _legacy_openapi() -> dict[str, Any]:
    app = FastAPI()
    mount_legacy_upload_probe(app)
    return app.openapi()


def test_production_does_not_advertise_retired_upload_or_file_operations() -> None:
    schema = create_app().openapi()
    for path, _ in _MULTIPART_OPERATIONS:
        assert path not in schema["paths"]
    assert "/backend-api/files" not in schema["paths"]
    assert all(
        "multipart/form-data" not in operation.get("requestBody", {}).get("content", {})
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict)
    )


def test_all_fastapi_multipart_operations_have_an_explicit_bounded_policy_surface() -> None:
    openapi = _legacy_openapi()
    actual = {
        (path, method)
        for path, path_item in openapi["paths"].items()
        for method, operation in path_item.items()
        if isinstance(operation, dict) and "multipart/form-data" in operation.get("requestBody", {}).get("content", {})
    }

    assert actual == _MULTIPART_OPERATIONS


def test_multipart_request_body_schemas_remain_semantically_identical() -> None:
    openapi = _legacy_openapi()

    assert _request_schema(openapi, "/api/accounts/import") == {
        "type": "object",
        "title": "Body_import_account_api_accounts_import_post",
        "required": ["auth_json"],
        "properties": {"auth_json": _binary("Auth Json")},
    }
    assert _request_schema(openapi, "/backend-api/transcribe") == {
        "type": "object",
        "title": "Body_backend_transcribe_backend_api_transcribe_post",
        "required": ["file"],
        "properties": {
            "file": _binary("File"),
            "prompt": _nullable_string("Prompt"),
        },
    }
    assert _request_schema(openapi, "/v1/audio/transcriptions") == {
        "type": "object",
        "title": "Body_v1_audio_transcriptions_v1_audio_transcriptions_post",
        "required": ["model", "file"],
        "properties": {
            "model": {"type": "string", "title": "Model"},
            "file": _binary("File"),
            "prompt": _nullable_string("Prompt"),
        },
    }

    optional_image_fields = {
        "model": "Model",
        "n": "N",
        "size": "Size",
        "quality": "Quality",
        "background": "Background",
        "output_format": "Output Format",
        "output_compression": "Output Compression",
        "moderation": "Moderation",
        "partial_images": "Partial Images",
        "stream": "Stream",
        "input_fidelity": "Input Fidelity",
        "user": "User",
    }
    image_properties = {field: _nullable_string(title) for field, title in optional_image_fields.items()}
    image_properties.update(
        {
            "prompt": {"type": "string", "title": "Prompt"},
            "image": _binary_array("Image"),
            "image[]": _binary_array("Image[]"),
            "mask": {
                "anyOf": [
                    {
                        "type": "string",
                        "contentMediaType": "application/octet-stream",
                    },
                    {"type": "null"},
                ],
                "title": "Mask",
            },
        }
    )
    assert _request_schema(openapi, "/v1/images/edits") == {
        "type": "object",
        "title": "Body_v1_images_edits_v1_images_edits_post",
        "required": ["prompt"],
        "properties": image_properties,
    }


def test_non_multipart_codex_image_and_file_surfaces_are_unchanged() -> None:
    openapi = _legacy_openapi()

    assert "/backend-api/codex/images/edits" not in openapi["paths"]
    files_body = openapi["paths"]["/backend-api/files"]["post"]["requestBody"]
    assert files_body == {
        "required": True,
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/FileCreateRequest"},
            }
        },
    }
