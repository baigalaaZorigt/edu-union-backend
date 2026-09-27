"""ORM-ийн суурь класс ба утгыг хөрвүүлэх багана төрлүүд."""
from sqlalchemy import Integer, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class Int(TypeDecorator):
    """INTEGER багана — DB рүү илгээхийн өмнө утгыг int болгоно.

    URL-ийн шүүлт (`?holboo_id=1`) болон JSON (`"structure_id": "5"`) текстээр ирдэг.
    SQLite үүнийг чимээгүй тэвчдэг, Postgres `integer = varchar` алдаа өгдөг — энд
    нэг дор шийднэ: "5" -> 5; тоо биш текст -> NULL (харьцуулалт таарахгүй, лавлах олдохгүй
    — SQLite-ийн хуучин зан төлөвтэй ижил); bool өөрчлөгдөхгүй.
    """
    impl = Integer
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, (int, bool)):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else value
        try:
            return int(str(value).strip())
        except ValueError:
            return None

    def coerce_compared_value(self, op, value):
        return self                      # `col == "5"` ч энэ хөрвүүлэлтээр явна


class Str(TypeDecorator):
    """TEXT багана — тоо ирвэл текст болгоно (SQLite-ийн TEXT affinity-тэй ижил)."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None or isinstance(value, str):
            return value
        return str(value)

    def coerce_compared_value(self, op, value):
        return self


class Base(DeclarativeBase):
    """Бүх model-ийн эх. `to_dict()` нь хуучин `dict(row)`-тэй ижил: бүх багана, нэрээр нь."""

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in self.__table__.columns}
