"""Effective upstream identity for both account-backed and source-backed history."""

from sqlalchemy import ColumnElement, func

from app.db.models import RequestLog


def request_source_id_expr() -> ColumnElement[str | None]:
    return func.coalesce(RequestLog.account_id, RequestLog.model_source_id)
