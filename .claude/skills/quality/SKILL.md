---
name: quality
description: edu-union-backend-ийн чанарын урсгал — стандарт, lint, refactor, code review, тест. Код бичсэн/өөрчилсний дараа, commit/push-ээс өмнө, "шалга", "review хий", "refactor хий", "lint", "тест ажиллуул", "стандартад нийцүүл" гэвэл ашиглана. Аргумент: check | lint | test | review | refactor <файл/хавтас> | all (анхдагч: all).
---

# Чанарын урсгал (edu-union-backend)

Аргумент (`$ARGUMENTS`) аль алхмыг хийхийг заана. Хоосон бол `all` — дарааллаар нь бүгдийг.

| Аргумент | Юу хийх |
|---|---|
| `check` / `lint` | `bash scripts/check.sh --fast` — lint + бүтцийн дүрэм |
| `test` | `bash scripts/check.sh` (+ API/схем өөрчлөгдсөн бол `--pg`) |
| `review` | Доорх **Review** жагсаалтаар өөрчлөлтийг шалгаж дүгнэлт гаргана |
| `refactor <зам>` | Доорх **Refactor** дүрмээр засаад, дараа нь `test` |
| `all` | review → (олдсоныг засах) → check → test |

Үр дүнг хэрэглэгчид **монголоор**, товч хүснэгт/жагсаалтаар тайлагна. Унасан зүйлийг нууж
болохгүй — гаралтыг нь хавсарга.

## 1. Стандарт (заавал)

CLAUDE.md бол үндсэн эх сурвалж; энд зөвхөн шалгах ёстой дүрмүүд:

- **`.py` файл ≤ 300 мөр.** Хэтэрвэл ижил import замтай багц болгоно (`__init__.py` нь `bp`
  үүсгээд дэд модулиудыг ДАРАА нь импортлож, гадагш хэрэгтэй нэрсийг re-export хийнэ).
- **SQL текст app кодод байхгүй** — бүх query SQLAlchemy 2.0 ORM (`core.orm.session()`).
  Схемийн өөрчлөлт = шинэ Alembic revision (`alembic/versions/000N_*.py`); `core/db/schema*.py`,
  `migrate*.py`, `pg*.py` царцсан — засахгүй.
- **`client/` ба `core/` нь `admin/`-аас импортлохгүй**; хоёр тал хэрэглэх зүйл → `core/`.
- **Шинэ blueprint → `run.py`-д бүртгэнэ.** Шинэ `/api/<resource>` → `PERMISSION_RESOURCES`
  (`core/db/reference_data.py`) — эс бөгөөс бүгд 403.
- **Soft delete:** устгал бүр `s.delete()` / `delete(Model)` — физик устгал, `?hard=1`-д ч
  бичихгүй. `select(*Model.__table__.c, ...)` бол заавал `.select_from(Model)` (эс бөгөөс
  устгасан мөр жагсаалтад гарна). Устгахад файлыг (`remove_upload`) арилгахгүй — зөвхөн
  засвараар солигдоход.
- **Холбоостой мөр:** шинэ лавлах/FK нэмбэл `core/orm/restrict.py`-ийн `RESTRICT`-д оруулна
  (эзэмшлийн каскад бол оруулахгүй).
- **Хариу:** алдаа `{"error": "..."}` монголоор, 400/401/403/404/409/422/429; update маршрут
  `PUT` ба `PATCH` хоёулаа; жагсаалт `?page=/per_page=` өгвөл `{items,total,page,per_page,pages}`
  (`paginate()` / `list_json()`), өгөөгүй бол массив.
- **Нууц:** `*.pem`, `.db_password`, `*accessKeys*.csv`, `.env` хэзээ ч commit/хэвлэхгүй.
- Код, коммент, алдааны мессеж — **монгол** (кирилл); тойрон буй кодын хэв маяг, коммент
  нягтралтай ижил.

## 2. Lint

```bash
bash scripts/check.sh --fast        # ruff + бүтцийн дүрмүүд
.venv/bin/ruff check . --fix        # автоматаар засагдах F401 гэх мэт
```

`ruff.toml`: `E9` (синтакс), `F` (pyflakes), `B` (bugbear). Хэв маягийн дүрэм (мөрийн урт,
import дараалал, `Optional`) санаатай оруулаагүй — **шинэ дүрэм нэмэхийн өмнө хэрэглэгчээс
асуу**, бөөн өөрчлөлт үүсгэдэг. ruff суугаагүй бол: `.venv/bin/pip install -r requirements-dev.txt`.

## 3. Refactor

1. Эхлээд **ногоон суурь**: `bash scripts/check.sh` давж байгаа эсэх. Унаж байвал refactor
   эхлүүлэхгүй, хэрэглэгчид хэл.
2. Зан төлөвийг **өөрчлөхгүй**: endpoint зам, blueprint/функцийн нэр (endpoint нэр), хариуны
   хэлбэр, статус код, алдааны текст хэвээр. Өөрчлөх шаардлага гарвал тусад нь асуу.
3. Нэг файл/сэдвээр нэг алхам: давхардлыг `common.py` / `core/*_core.py` руу гаргах, 300 мөр
   давсныг багц болгох, N+1-ийг нэг query болгох (`*_many()` загвар), ашиглагдахгүй кодыг хасах.
4. Алхам бүрийн дараа `bash scripts/check.sh`; эцэст нь query/схемд хүрсэн бол `--pg`.
5. CLAUDE.md-ийн "Project layout" / холбогдох хэсгийг шинэчил.

## 4. Review

`git diff` (эсвэл заасан commit/файл)-ыг уншиж, **жинхэнэ асуудлыг** л гарга — нотолгоотой,
файл:мөр, ямар оролтоор ямар буруу үр дүн гарахтай. Шалгах жагсаалт:

- **Зөв байдал:** `abort()`-оос өмнө commit хийгдсэн эсэх; `IntegrityError` → rollback + 409;
  `Int`/`Str` coercion (Postgres `integer = varchar`); `None`/хоосон мөр; timezone (`now_str()` UTC).
- **Эрх ба хүрээ:** шинэ зам зөв `resource.action` руу буух эсэх (`core/auth.py`
  `PATH_RESOURCE`/`SUB_RESOURCE`/`SUB_ACTION`); гишүүн/байгууллагын уншилт, бичилт
  `scope_core`-оор шүүгдсэн эсэх (`require_*_in_scope` → 403); `/api/portal/` токенгүй тул
  хувийн мэдээлэл задрахгүй байх.
- **Soft delete / restrict:** дээрх стандарт; нуугдсан мөр тоолол, хайлт, статистикт орохгүй.
- **Аюулгүй байдал:** URL-ийн схем (`javascript:`, `//host`) шалгалт; файлын төрөл/хэмжээ;
  HTML escape (хайлтын snippet); rate limit (`X-Real-IP`); нууц лог руу орохгүй.
- **Гүйцэтгэл:** гогцоон доторх query (N+1), бүх мөрийг санах ойд ачаалах, индексгүй шүүлт.
- **Тест ба баримт:** шинэ зан төлөвт pytest (`tests/test_<area>_<topic>.py`, fixture `api` /
  `anon` / `make_user`), Postman хүсэлт, CLAUDE.md шинэчлэгдсэн эсэх.

Олдсоныг ноцтой байдлаар эрэмбэлж, "засах уу?" гэж асуу. Жижиг хэв маягийн санал
(nit) тусад нь, товч.

## 5. Тест

```bash
bash scripts/check.sh               # lint + дүрэм + pytest (~20 с)
bash scripts/check.sh --pg          # + Postgres (docker): alembic upgrade, model drift 0,
                                    #   Postman ×2 (newman), серверийн лог 500-гүй (~3 мин)
```

- **pytest** — шинэ зан төлөв бүрд тест: өөрийн мөрөө үүсгэж, төгсгөлд нь устгана; мэдэгдэж
  буй алдааг `xfail(strict=True)`. Бүхэлд нь SQLite дээр — Postgres-ийн ялгааг `--pg` барина.
- **Postman** (`docs/edu-union-backend.postman_collection.json`) — шинэ endpoint бүрд хүсэлт:
  фолдер бүр `Нэмэх` → `{{new_*}}` хадгалж, `Засах` + `— PATCH-аар мөн` ихэр, `Устгах`;
  seed мөрийг хэзээ ч засах/устгахгүй; `/api/portal/` хүсэлт `"auth": {"type": "noauth"}`;
  script-ийн хувьсагч `var` (нэг sandbox); давтан ажиллуулахад ногоон байх ёстой (2 удаа).
  Тоо өөрчлөгдвөл CLAUDE.md-ийн "N requests, ~M assertions"-ийг шинэчил.
- API, query эсвэл схемд хүрсэн өөрчлөлтийг **push-ээс өмнө `--pg`-ээр** шалга.
- Push хийсний дараа CI (`gh run watch`) — тест + deploy амжилттай эсэх, дараа нь
  `https://api.fmesu.mn/api/portal/menu` → 200.

## Анхаар

- Commit/push зөвхөн хэрэглэгч хүссэн үед (`main` руу push = production deploy).
- Шинэ dependency, CI-ийн өөрчлөлт, хэв маягийн шинэ lint дүрэм — эхлээд асуу.
