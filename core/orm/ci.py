"""ci_lower(x) — Кирилл зөв ажилладаг жижиг үсэг (том/жижиг үсэг үл ялгах LIKE-д).

SQLite-ийн lower() зөвхөн ASCII-г хөрвүүлдэг тул SQLite холболт бүрд Python-ий str.lower()-г
`ci_lower` нэрээр бүртгэнэ (core/orm/__init__.py); Postgres дээр энгийн lower() (UTF-8 locale-д
Кирилл зөв). Хайх утгыг Python талд .lower() хийгээд `ci_lower(col).contains(v, autoescape=True)`.
"""
from sqlalchemy import String
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.functions import GenericFunction


class ci_lower(GenericFunction):
    type = String()
    name = "ci_lower"
    inherit_cache = True


@compiles(ci_lower, "postgresql")
def _pg_lower(element, compiler, **kw):
    return "lower(%s)" % compiler.process(element.clauses, **kw)


def sqlite_lower(value):
    return value.lower() if isinstance(value, str) else value
