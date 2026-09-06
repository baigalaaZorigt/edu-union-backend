# News Content API Specification — V1.1

## 1. Scope

Мэдээ, зар (News) — картлаг жагсаалт + дотор нь чөлөөт блокоор зохиосон контент.
Блок систем нь одоо байгаа Цэсний `page` / `page_block` бүтэцтэй яг адилхан тул
frontend-ийн блок засварлагч (Текст/Зураг/Видео/Файл/Холбоос) шинээр бичихгүйгээр
дахин ашиглагдана.

Frontend аль хэдийн бэлэн (`app/(admin)/news/page.tsx`) — зөвхөн backend хүлээж байна.

---

## 2. Database Structure

```text
news
 └── news_block

menus   (одоо байгаа хүснэгт, 1 багана нэмнэ)
```

### news

```sql
CREATE TABLE news (
    id BIGSERIAL PRIMARY KEY,

    title VARCHAR(500) NOT NULL,
    category VARCHAR(20) NOT NULL,   -- 'Мэдээ' | 'Сургалт'
    author VARCHAR(200),
    cover_image_url TEXT,
    summary TEXT,

    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- 'draft' | 'published'
    published_at TIMESTAMP NULL,

    created_by BIGINT NULL,
    updated_by BIGINT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL
);
```

`category` validation: `in:Мэдээ,Сургалт` — өөр утга ирвэл 422.
`status = 'published'` болоход `published_at`-г сервер автоматаар тавина.

### news_block

`page_block`-той 1:1 ижил бүтэц, зөвхөн FK нь `news_id`.

```sql
CREATE TABLE news_block (
    id BIGSERIAL PRIMARY KEY,

    news_id BIGINT NOT NULL,
    type VARCHAR(20) NOT NULL,   -- 'text' | 'image' | 'video' | 'file' | 'link'
    sort_order INTEGER NOT NULL DEFAULT 0,

    text TEXT NULL,              -- type=text
    url TEXT NULL,                -- type=image/video/file/link
    caption TEXT NULL,            -- type=image
    title TEXT NULL,              -- type=video/link
    name VARCHAR(255) NULL,       -- type=file
    mime_type VARCHAR(100) NULL,  -- type=file
    size BIGINT NULL,             -- type=file

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NULL,

    CONSTRAINT fk_news_block_news
        FOREIGN KEY (news_id)
        REFERENCES news(id)
        ON DELETE CASCADE
);
```

### menus (add column)

```sql
ALTER TABLE menus ADD COLUMN news_category VARCHAR(20) NULL;
-- 'Мэдээ' | 'Сургалт' | NULL (= бүх ангилал)
-- Зөвхөн type='news' цэсэнд хэрэглэгдэнэ.
```

---

## 3. Block Types

Цэсний page_block-той адилхан 5 төрөл:

```text
text   { text }
image  { url, caption }
video  { url, title }
file   { url, name, mime_type, size }
link   { url, title }
```

---

## 4. Admin API

### news

```http
GET    /api/admin/news
```
Query: `search`, `category` (Мэдээ | Сургалт), `status`, `page`, `per_page`

```http
POST   /api/admin/news
```
```json
{
  "title": "Гишүүнчлэлийн шинэчилсэн бүртгэл эхэллээ",
  "category": "Мэдээ",
  "author": "Д. Батаа",
  "cover_image_url": "https://.../uploads/2026/08/cover.jpg",
  "summary": "Товч танилцуулга",
  "status": "draft"
}
```
Blocks-гүйгээр эхлээд үүсгэнэ — карт мэдээллийг эхэлж хадгалаад, дараа нь блок нэмнэ.

```http
GET    /api/admin/news/{id}
```
Нэг мэдээ + `blocks` массив хамт.

```http
PUT    /api/admin/news/{id}
DELETE /api/admin/news/{id}
```
DELETE нь мэдээ болон бүх блокийг cascade устгана.

### news_block

```http
GET    /api/admin/news/{newsId}/blocks
POST   /api/admin/news/{newsId}/blocks
```
POST body: `{ type, ...төрлийн талбарууд }` — жишээ:
```json
{ "type": "image", "url": "https://.../photo.jpg", "caption": null }
```

```http
PUT    /api/admin/news_blocks/{id}
DELETE /api/admin/news_blocks/{id}
```

```http
PUT    /api/admin/news/{newsId}/blocks/reorder
```
```json
{ "order": [ { "id": 501, "sort_order": 1 }, { "id": 502, "sort_order": 2 } ] }
```
(`page_block/reorder`-той ижил хэлбэр)

### upload

Шинэ endpoint шаардлагагүй — одоо байгаа `POST /api/upload`-г ковер зураг болон
блок доторх зураг/файлд хоёуланд нь ашиглана. Хариу: `{ url, name, mime_type, size }`.

---

## 5. Response Examples

**GET /api/admin/news**
```json
{
  "data": [
    {
      "id": 41,
      "title": "Гишүүнчлэлийн шинэчилсэн бүртгэл эхэллээ",
      "category": "Мэдээ",
      "author": "Д. Батаа",
      "cover_image_url": "https://.../uploads/2026/08/cover.jpg",
      "status": "published",
      "published_at": "2026-06-12 09:00:00"
    }
  ],
  "total": 1, "per_page": 20, "current_page": 1
}
```

**GET /api/admin/news/41**
```json
{
  "id": 41,
  "title": "Гишүүнчлэлийн шинэчилсэн бүртгэл эхэллээ",
  "category": "Мэдээ",
  "status": "published",
  "blocks": [
    { "id": 501, "type": "text", "text": "<p>Энэ сарын 12-наас...</p>", "sort_order": 1 },
    { "id": 502, "type": "image", "url": "https://.../hall.jpg", "caption": null, "sort_order": 2 }
  ]
}
```

---

## 6. Portal API — no auth

`/api/portal/...`-той адилхан `auth='noauth'`-тэй.

```http
GET /api/portal/news
```
Query: `category` (Мэдээ | Сургалт, өгөгдөөгүй бол бүгд), `page` — зөвхөн
`status=published` мэдээ буцаана.

```http
GET /api/portal/news/{id}
```
`blocks` хамт — draft мэдээнд 404 буцаана.

---

## 7. Menu Integration — one menu per category

Одоо байгаа Цэсний удирдлагад "Мэдээ" төрлийн цэс аль хэдийн бий
(`type=news`, систем удирдана, өөрийн блок агуулгагүй).

Admin **2 тусдаа "Мэдээ" төрлийн цэс** үүсгэнэ:
- "Мэдээ" цэс → `news_category = "Мэдээ"`
- "Сургалт" цэс → `news_category = "Сургалт"`

Портал эдгээрийг тус тусад нь харуулж, дарахад `GET /portal/news?category=...`-г
харгалзах ангиллаар нь дуудна. `news_category = null` бол хуучин байдлаараа бүх
ангиллын мэдээг харуулна (одоо байгаа цэс эвдэрэхгүй).

---

## 8. Implementation Order

1. **Migration** — `news`, `news_block` хүснэгт (`page`/`page_block`-ийг хуулж, FK нэрийг сольж болно); `menus`-д `news_category` багана нэмэх
2. **Validation** — `news.category` нь `in:Мэдээ,Сургалт`
3. **NewsController** — `PageController`/`PageBlockController`-ийг загвар болгож `news_id`-д тааруулах
4. **Reorder endpoint** — `page_block/reorder`-тэй ижил логик
5. **Portal endpoints** — noauth, зөвхөн published, `category`-аар шүүнэ
6. **Frontend** — аль хэдийн бэлэн, зөвхөн backend холбогдохыг хүлээж байна
