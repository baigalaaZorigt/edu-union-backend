"""Soft delete — БҮХ хүснэгт. Устгасан мөр DB-д үлдэж, API-аас бүрэн алга болно.

Хэрэглэгчийн код ердийнхөөрөө `session.delete(obj)` / `session.execute(delete(Model)...)`
бичнэ — энд тэдгээрийг барьж авна:

* УНШИЛТ: ORM SELECT / UPDATE / DELETE бүрд `deleted_at IS NULL` автоматаар нэмэгдэнэ
  (`with_loader_criteria`, JOIN ба дэд query-д ч). Устгасныг харах шаардлагатай газар
  (seed, migration) `execution_options(include_deleted=True)` эсвэл
  `session.info["include_deleted"] = True`.
* УСТГАЛ: мөрийг устгахын оронд `deleted_at`-ийг бөглөнө, мөн:
    - DB-ийн ON DELETE CASCADE-ийг model metadata-аас уншиж давтана (хүүхэд мөрүүдийг мөн
      soft delete); SET NULL-ийг ДАВТАХГҮЙ — эх мөр үлддэг тул created_by зэрэг хэвээр;
    - полиморф `contact` (owner_type/owner_id, FK-гүй) — эзэн нь устахад хамт;
    - UNIQUE текст утгыг (username, slug, code, name ...) `~deleted~<id>` залгаж чөлөөлнө —
      ижил нэр/кодоор дахин үүсгэж болно.
  Файл (S3/диск) УСТГАХГҮЙ — мөр нуугдсан ч өгөгдөл хадгалагдана.
* ДАХИН ҮҮСГЭХ: байгалийн / гараар өгсөн түлхүүртэй шинэ мөр (аймгийн код, role_permission,
  user_scope, лавлахын id) устгасан мөртэй давхцвал тэр НУУГДСАН мөрийг физикээр сольж
  шинээр бичнэ (before_flush) — эс бөгөөс PK зөрчил гарна.
"""
from datetime import datetime, timezone

from sqlalchemy import Join, String, Table, event, inspect, select, tuple_, update
from sqlalchemy.orm import Session, with_loader_criteria

from core.orm.base import Base

DELETED_SUFFIX = "~deleted~"
# Полиморф холбоос: эзэн хүснэгт -> contact.owner_type утга (FK-гүй тул metadata-д алга)
POLYMORPHIC_OWNERS = {"horoo", "organization", "member"}


def _now():
    """core.helpers.now_str()-тэй ижил: UTC "YYYY-MM-DD HH:MM:SS"."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _soft_models():
    return [m.class_ for m in Base.registry.mappers if "deleted_at" in m.class_.__table__.c]


def _model_of(table_name):
    for m in Base.registry.mappers:
        if m.class_.__table__.name == table_name:
            return m.class_
    return None


def _unique_text_columns(model):
    """Ганц баганатай UNIQUE текст баганууд (чөлөөлөх шаардлагатай)."""
    t = model.__table__
    cols = set()
    for c in t.constraints:
        if type(c).__name__ == "UniqueConstraint" and len(c.columns) == 1:
            cols |= {col.name for col in c.columns}
    for ix in t.indexes:
        if ix.unique and len(ix.columns) == 1:
            cols |= {col.name for col in ix.columns}
    cols |= {c.name for c in t.columns if c.unique}
    return [c for c in cols if _is_text(t.c[c])]


def _is_text(column):
    t = column.type
    return isinstance(getattr(t, "impl_instance", t), String)       # Str TypeDecorator ч


def _children(model):
    """model-ийг заасан FK-ууд: [(хүүхэд model, хүүхдийн багана, эцгийн багана, ondelete)]."""
    out = []
    table = model.__table__
    for m in Base.registry.mappers:
        for fk in m.class_.__table__.foreign_keys:
            if fk.column.table is table:
                out.append((m.class_, fk.parent.name, fk.column.name, (fk.ondelete or "").upper()))
    return out


def soft_delete(s, obj, ts=None):
    """Нэг объектыг (ба каскадаар хүүхдүүдийг) soft delete хийнэ."""
    if obj is None or getattr(obj, "deleted_at", None):
        return
    from core.orm.restrict import check_references       # models-ийг импортлодог тул энд
    check_references(s, obj)                               # холбоостой бол 409
    ts = ts or _now()
    model = type(obj)
    obj.deleted_at = ts
    pk = inspect(obj).identity or tuple(getattr(obj, c.key) for c in inspect(model).primary_key)
    for col in _unique_text_columns(model):
        val = getattr(obj, col)
        if val is not None and DELETED_SUFFIX not in str(val):
            setattr(obj, col, f"{val}{DELETED_SUFFIX}{'-'.join(str(p) for p in pk)}")
    for child, fk_col, parent_col, ondelete in _children(model):
        value = getattr(obj, parent_col)
        if ondelete == "CASCADE":
            for c in s.scalars(select(child).where(getattr(child, fk_col) == value)):
                soft_delete(s, c, ts)
        # SET NULL-ийг давтахгүй: эх мөр DB-д (нуугдаад) үлддэг тул лавлагаа хүчинтэй —
        # ж: хэрэглэгч устсан ч news.created_by хэвээр (аудит). Лавлах/бүртгэлийн SET NULL
        # холбоосыг core/orm/restrict.py өмнө нь 409-өөр хаадаг тул NULL болох мөр үлддэггүй.
    if model.__table__.name in POLYMORPHIC_OWNERS:
        contact = _model_of("contact")
        for c in s.scalars(select(contact).where(contact.owner_type == model.__table__.name,
                                                 contact.owner_id == obj.id)):
            soft_delete(s, c, ts)


class SoftSession(Session):
    """`delete(obj)` нь soft delete хийдэг session."""

    def delete(self, instance):
        soft_delete(self, instance)


def _include_deleted(state):
    return state.execution_options.get("include_deleted") or state.session.info.get("include_deleted")


@event.listens_for(SoftSession, "do_orm_execute")
def _orm_execute(state):
    if _include_deleted(state):
        return None
    if state.is_delete and not state.execution_options.get("hard"):
        # delete(Model).where(...) -> тохирох мөр бүрийг soft delete (каскадтай), rowcount хэвээр
        model = _model_of(state.statement.table.name)
        rows = state.session.scalars(
            select(model).where(state.statement.whereclause)
            if state.statement.whereclause is not None else select(model)).all()
        ts = _now()
        for obj in rows:
            soft_delete(state.session, obj, ts)
        state.session.flush()
        pk = inspect(model).primary_key
        keys = [tuple(getattr(o, c.key) for c in pk) for o in rows]
        if len(pk) == 1:
            cond = pk[0].in_([k[0] for k in keys])
        else:                                             # нийлмэл PK (role_permission)
            cond = tuple_(*pk).in_(keys) if keys else pk[0].in_([])
        return state.invoke_statement(
            statement=update(model).where(cond).values(deleted_at=ts)
            .execution_options(include_deleted=True, synchronize_session=False))
    if state.is_select:
        state.statement = _filter_core_froms(state.statement)
    if state.is_select or state.is_update or state.is_delete:
        state.statement = state.statement.options(*[
            with_loader_criteria(m, lambda cls: cls.deleted_at.is_(None), include_aliases=True)
            for m in _soft_models()])
    return None


def _filter_core_froms(stmt):
    """with_loader_criteria-г гүйцээнэ: ORM entity-гүй, ЦЭВЭР Table-аар эхэлсэн FROM
    (ж: `select(*Model.__table__.c)`, `select_from(Model.__table__)`) -> WHERE deleted_at IS NULL.

    Join-ийн зөвхөн зүүн (үндсэн) хүснэгтэд — баруун талд WHERE нэмбэл OUTER JOIN эвдэрнэ.
    Дэд query-д хүрэхгүй тул шинэ код `select_from(Model)`-оор ORM entity өгөх нь зөв.
    """
    orm = {getattr(d.get("entity"), "__table__", None) for d in stmt.column_descriptions}
    for f in stmt.get_final_froms():
        while isinstance(f, Join):
            f = f.left
        if isinstance(f, Table) and "deleted_at" in f.c and not f._annotations and f not in orm:
            stmt = stmt.where(f.c.deleted_at.is_(None))
    return stmt


def _unique_keys(model):
    """PK + UNIQUE (constraint / index / багана) баганын бүлгүүд."""
    t = model.__table__
    keys = [[c.name for c in t.primary_key.columns]]
    for c in t.constraints:
        if type(c).__name__ == "UniqueConstraint":
            keys.append([col.name for col in c.columns])
    keys += [[col.name for col in ix.columns] for ix in t.indexes if ix.unique]
    keys += [[c.name] for c in t.columns if c.unique]
    return keys


@event.listens_for(SoftSession, "before_flush")
def _replace_hidden_duplicates(s, _ctx, _instances):
    """Шинэ мөрийн PK/UNIQUE утга НУУГДСАН мөртэй давхцвал нуугдсаныг физикээр сольно.

    Ж: устгасан аймгийн кодыг дахин үүсгэх, role_permission-ийг дахин оноох,
    user_scope-ийг дахин хадгалах, хуудасгүй болсон цэсэнд page үүсгэх (page.menu_id UNIQUE).
    """
    for obj in list(s.new):
        model = type(obj)
        table = model.__table__
        if "deleted_at" not in table.c:
            continue
        for cols in _unique_keys(model):
            vals = [getattr(obj, table.c[c].key, None) for c in cols]
            if any(v is None for v in vals):
                continue
            cond = [table.c[c] == v for c, v in zip(cols, vals)]
            hidden = s.connection().execute(select(table.c.deleted_at).where(*cond)).first()
            if hidden is not None and hidden[0] is not None:
                s.connection().execute(table.delete().where(*cond))
