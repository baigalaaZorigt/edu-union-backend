"""Аудит — created_by / updated_by-г session өөрөө бөглөнө (handler бүрд код бичихгүй).

`g.user` (core/auth.py) байгаа хүсэлтэд:
* шинэ мөр (`s.add(obj)`)                 -> created_by (өөрөө өгөөгүй бол)
* өөрчлөгдсөн мөр (soft delete ч мөн)       -> updated_by
* `update(Model).values(...)` бөөн шинэчлэл -> updated_by

Нэвтрээгүй хүсэлт (портал, /api/login), seed, скрипт — хэн болох нь мэдэгдэхгүй тул
хөндөхгүй (портлоос ирсэн санал/гомдлын created_by NULL хэвээр).
"""
from flask import g, has_request_context
from sqlalchemy import event

from core.orm.soft import SoftSession, _model_of


def current_user_id():
    """Нэвтэрсэн хэрэглэгчийн id (хүсэлтээс гадуур / зочин бол None)."""
    if not has_request_context():
        return None
    return (g.get("user") or {}).get("id")


@event.listens_for(SoftSession, "before_flush")
def _stamp_objects(s, _ctx, _instances):
    uid = current_user_id()
    if uid is None:
        return
    for obj in s.new:
        if "created_by" in obj.__table__.c and obj.created_by is None:
            obj.created_by = uid
    for obj in s.dirty:
        if "updated_by" in obj.__table__.c and s.is_modified(obj):
            obj.updated_by = uid


@event.listens_for(SoftSession, "do_orm_execute")
def _stamp_bulk_update(state):
    if not state.is_update:
        return
    uid = current_user_id()
    model = _model_of(state.statement.table.name)
    if uid is not None and model is not None and "updated_by" in model.__table__.c:
        state.statement = state.statement.values(updated_by=uid)
