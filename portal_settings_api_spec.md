# Порталын тохиргоо — API тодорхойлолт
**(Portal Settings — API Specification)**

Version 1.0 · frontend UI бэлэн (`/portal-settings`), backend API одоогоор алга

---

## 1. Зорилго

Порталын (`public/portal.html`) толгой хэсэг, нүүр хуудасны баннер, холбоо барих мэдээлэл, хаяг/газрын зургийг админ талаас нэг дороос удирдах. Одоогоор эдгээр утгууд portal.html-д **хатуу бичигдсэн** (hardcoded) байгаа тул админ хэсгээс өөрчлөх боломжгүй.

Frontend талд `/portal-settings` хуудас бэлэн, гэхдээ бүх талбар зөвхөн локал state дээр ажиллаж байгаа тул хадгалсан ч юу ч өөрчлөгдөхгүй, шинэчлэхэд алга болно. Энэ спек тэр хуудсыг бодит API-тай холбоход зориулагдсан.

---

## 2. Өгөгдлийн бүтэц

### 2.1 `portal_settings` — singleton (нэг мөр)

Хэрэглэгч бүрийн биш, **бүхэл системд нэг** тохиргооны мөр байна — жагсаалт, CRUD хэрэггүй, зөвхөн уншиж/бүхэлд нь дарж хадгална.

| Талбар | Төрөл | Тайлбар |
|---|---|---|
| `logo_url` | string \| null | `/api/upload`-аас ирсэн байнгын URL |
| `header_title` | string | Лого хажуугийн гарчиг |
| `header_subtitle` | string | Лого хажуугийн дэд гарчиг |
| `hero_badge` | string | Нүүр баннерын дээд тэмдэглэгээ |
| `hero_title` | string | Нүүр баннерын гарчиг |
| `hero_text` | string | Нүүр баннерын тайлбар (урт текст) |
| `phones` | string[] | Утасны дугаарууд, жагсаалт |
| `website` | string \| null | жишээ: `fmesu.mn` |
| `facebook_url` | string \| null | |
| `youtube_url` | string \| null | |
| `address` | string | Хаягийн бүтэн текст |
| `map_embed_url` | string \| null | Google Maps `embed` iframe-ийн src URL |
| `updated_at` | datetime | |

> **Санал:** `phones`-ийг JSON багана байдлаар хадгал (энгийн массив, тусад нь хүснэгт хэрэггүй).

---

## 3. Endpoints

### 3.1 Админ (эрх шаардана)

| Method | Path | Тайлбар |
|---|---|---|
| GET | `/api/portal_settings` | Одоогийн тохиргоог буцаана. Мөр байхгүй бол анхны утгуудаар автоматаар үүсгэж болно (доор §5). |
| PUT | `/api/portal_settings` | Тохиргоог **бүхэлд нь** дарж хадгална (frontend бүх талбараа мэднэ тул тусад нь PATCH хэрэггүй). |

### 3.2 Портал (нээлттэй, эрх шаардахгүй)

| Method | Path | Тайлбар |
|---|---|---|
| GET | `/api/public/portal_settings` | `portal.html`-ийг динамик болгоход ашиглана. Ижил бүтэц, зөвхөн auth шаардахгүй. |

> Одоогийн `/api/public/menu`, `/api/public/page/{slug}` -тэй адил хэв маягийг баримтална.

---

## 4. Лого байршуулах

Тусдаа endpoint хэрэггүй — одоо байгаа **`POST /api/upload`**-ийг дахин ашиглана (Цэсний блок-контентод хэрэглэдэгтэй ижил):

```
POST /api/upload
Content-Type: multipart/form-data, field name: "file"

Response:
{ "url": "https://.../uploads/2026/08/logo.png", "name": "logo.png", "mime_type": "image/png", "size": 48213 }
```

Хариунд ирсэн `url`-ийг `PUT /api/portal_settings`-ийн `logo_url` талбарт дамжуулна. Зураг ≤5MB (jpg/png/webp) гэсэн одоогийн `/api/upload`-ын хязгаарлалт хүчинтэй.

---

## 5. Жишээ payload

### GET /api/portal_settings

```json
{
  "logo_url": "https://.../uploads/2026/08/logo.png",
  "header_title": "МБШУ-ны ҮЭ-ийн Холбоо",
  "header_subtitle": "Хөдөлмөрийн хүний төлөө",
  "hero_badge": "1924 оноос эхлэлтэй салбарын үйлдвэрчний эвлэлийн холбоо",
  "hero_title": "Боловсрол, шинжлэх ухааны салбарын ажилтнуудын эрх ашгийн төлөө",
  "hero_text": "Монголын Боловсрол, Шинжлэх Ухааны Үйлдвэрчний Эвлэлийн Холбоо нь салбарын ажилтнуудын хөдөлмөрлөх эрх, хууль ёсны ашиг сонирхлыг хамгаалах, нийгмийн баталгааг сайжруулах зорилготой нэгдэл юм.",
  "phones": ["323555", "313609", "326328", "70126927"],
  "website": "fmesu.mn",
  "facebook_url": "https://www.facebook.com/groups/1629671727055980/",
  "youtube_url": null,
  "address": "210646 Улаанбаатар хот, Чингэлтэй дүүрэг, 1-р хороо, Бага тойруу /15160/, Сүхбаатарын талбай, МҮЭ-ийн ордон 221, 315, 316, 317 тоот",
  "map_embed_url": "https://www.google.com/maps/embed?pb=...",
  "updated_at": "2026-08-21T09:14:00Z"
}
```

### PUT /api/portal_settings

Яг GET-тэй ижил бүтэц (`updated_at`-гүйгээр) — бүх талбарыг илгээнэ:

```json
{
  "logo_url": "https://.../uploads/2026/08/logo.png",
  "header_title": "МБШУ-ны ҮЭ-ийн Холбоо",
  "header_subtitle": "Хөдөлмөрийн хүний төлөө",
  "hero_badge": "...",
  "hero_title": "...",
  "hero_text": "...",
  "phones": ["323555", "313609"],
  "website": "fmesu.mn",
  "facebook_url": "https://facebook.com/...",
  "youtube_url": "",
  "address": "...",
  "map_embed_url": "https://www.google.com/maps/embed?..."
}
```

---

## 6. Валидаци, хязгаарлалт

- `phones`: дор хаяж **1** дугаар байх ёстой (frontend аль хэдийн шалгадаг, backend талд давхар шалгах нь зүйтэй).
- `website`, `facebook_url`, `youtube_url`, `map_embed_url`: хоосон эсвэл зөв URL байх (`http`/`https`).
- `map_embed_url`: Google Maps-ийн `embed` төрлийн URL байх ёстой (iframe `src`-д шууд ашиглагдана тул хортой script-тэй URL зөвшөөрөхгүй байх нь зүйтэй).
- Текст талбарууд (`hero_text`, `address` гэх мэт) урт байж болно — max length хатуу хязгаарлах шаардлагагүй, гэхдээ санал болгож буй дээд хэмжээ: 2000 тэмдэгт.

---

## 7. Permission кодууд (санал)

```
portal_settings.read
portal_settings.update
```

`/api/public/portal_settings` эрх шаардахгүй тул дээрх кодод хамаарахгүй.

---

## 8. Backend-д анхаарах зүйлс

- Энэ бол **singleton** тул `id` дамжуулах, сонгох шаардлагагүй — систем доторх ганц мөрийг GET/PUT хийнэ.
- Мөр байхгүй анхны ачаалалд (эхний деплой) `GET`-ийг дуудахад автоматаар анхны утгуудаар (одоогийн `portal-settings/page.tsx`-д seed хийсэн утгууд, §5-ын жишээтэй ижил) мөр үүсгэвэл frontend тал өөрчлөлтгүйгээр ажиллана.
- `PUT` амжилттай болмогц `/api/public/portal_settings`-д шинэчлэгдсэн утга шууд харагдах ёстой — кэштэй бол богино TTL (жишээ нь 60 секунд) тавихыг санал болгож байна, учир нь портал талд бараг бодит цагийн шинэчлэлт хэрэгтэй биш.
- `public/portal.html` өөрөө одоогоор бүрэн статик тул энэ API бэлэн болсны дараа тухайн хуудсыг эдгээр утгыг динамикаар татаж харуулах болгон дахин зохиох хэрэгтэй болно (энэ бол тусдаа ажил, энд хамаарахгүй).
