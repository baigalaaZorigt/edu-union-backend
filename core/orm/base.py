"""ORM-ийн суурь класс."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Бүх model-ийн эх. `to_dict()` нь хуучин `dict(row)`-тэй ижил: бүх багана, нэрээр нь."""

    def to_dict(self):
        return {c.key: getattr(self, c.key) for c in self.__table__.columns}
