# Санал хүсэлт, Өргөдөл гомдол — API Specification V1

## 1. Зорилго

Портал дээрх 2 бие даасан, жижиг маягт:
- **Санал хүсэлт** — Нэр, И-мэйл, Утас, Санал хүсэлт (текст)
- **Өргөдөл, гомдол** — Нэр, И-мэйл, Утас, Тайлбар, Хавсралт (файл, заавал биш)

Survey/Poll/News шиг том "engine" биш тул **2 энгийн хүснэгт** хангалттай — нэг дундын
загвар руу оруулах шаардлагагүй. Admin талд одоо `app/(admin)/feedback/page.tsx` дээр 2
tab-тай (жагсаалт + дэлгэрэнгүй харах) статик mockup бэлэн.

## 2. Өгөгдлийн бүтэц

### suggestions

```sql
CREATE TABLE suggestions (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'new',  -- 'new' | 'reviewed'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### complaints

```sql
CREATE TABLE complaints (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    file_url TEXT NULL,
    file_name VARCHAR(255) NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'new',  -- 'new' | 'reviewed'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

`status` нь V1-д заавал шаардлагагүй ("шинэ" гэдгийг тод харуулах бол хэрэгтэй байж болно) —
одоогийн mockup UI үүнийг ашиглахгүй байгаа тул сонголтоор орхив.

## 3. Portal API — токенгүй (маягт илгээх)

```http
POST /api/portal/suggestions
```
```json
{ "name": "Б. Оюунчимэг", "email": "oyunchimeg@example.mn", "phone": "99112233", "message": "Гишүүдийн хурлыг жилд 2 удаа зохион байгуулах хэрэгтэй байна." }
```
Хариу: `201 { "status": true, "message": "Таны санал хүсэлт бүртгэгдлээ." }`

```http
POST /api/portal/complaints
```
```json
{ "name": "Т. Батжаргал", "email": "batjargal@example.mn", "phone": "91234567", "description": "Цалингийн зөрчилтэй холбоотой гомдол.", "file_url": "https://.../uploads/2026/09/gomdol.pdf", "file_name": "gomdol_batjargal.pdf" }
```
`file_url`/`file_name` заавал биш. Файл эхлээд одоо байгаа **`POST /api/upload`**-аар
байршуулж (өөр upload endpoint шинээр хэрэггүй), буцаж ирсэн `url`-ийг энд дамжуулна —
Мэдээ, Цэсний блок дээр ашигладагтай яг адилхан урсгал.

## 4. Admin API

```http
GET /api/admin/suggestions
```
Query: `search`, `page`, `per_page`.
```json
{
  "items": [
    { "id": 1, "name": "Б. Оюунчимэг", "email": "oyunchimeg@example.mn", "phone": "99112233", "message": "...", "created_at": "2026-09-01 10:00:00" }
  ],
  "page": 1, "pages": 1, "per_page": 20, "total": 1
}
```

```http
GET /api/admin/complaints
```
Query: `search`, `page`, `per_page`.
```json
{
  "items": [
    { "id": 1, "name": "Т. Батжаргал", "email": "batjargal@example.mn", "phone": "91234567", "description": "...", "file_url": "https://.../gomdol.pdf", "file_name": "gomdol_batjargal.pdf", "created_at": "2026-09-03 09:00:00" }
  ],
  "page": 1, "pages": 1, "per_page": 20, "total": 1
}
```

```http
DELETE /api/admin/suggestions/{id}
DELETE /api/admin/complaints/{id}
```

Тус бүрдээ жагсаалтын хариунд аль хэдийн бүх талбар (message/description хамт) орсон тул
**тусдаа "нэгийг авах" endpoint шаардлагагүй** — admin-ийн 👁 дэлгэрэнгүй харах модаль нь
жагсаалтаас аль хэдийн татсан датагаа шууд харуулна.

## 5. Валидаци

- `name`, `email`, `phone` — 2 маягтад аль алинд нь заавал.
- `message` (suggestions) / `description` (complaints) — заавал.
- `file_url`/`file_name` (complaints) — заавал биш.
- `email` формат шалгах; `phone` тоо орлуулга шалгах (Монголын дугаарын урттай).

## 6. Хэрэгжүүлэх дараалал

1. **Migration** — `suggestions`, `complaints` хүснэгт
2. **Portal endpoints** — noauth, `POST /portal/suggestions`, `POST /portal/complaints`
3. **Admin endpoints** — `GET /admin/suggestions`, `GET /admin/complaints`, `DELETE` хоёуланд нь
4. **Frontend** — `app/(admin)/feedback/page.tsx`-ийн `SEED_SUGGESTIONS`/`SEED_COMPLAINTS`-г эдгээр
   `GET` дуудалтаар сольж, устгах товчийг `DELETE`-тэй холбоно (өөрчлөлт багатай)
