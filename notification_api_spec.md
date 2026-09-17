# Мэдэгдэл (Notification) — API Specification V1

## 1. Зорилго

Одоо 2 газар mock дата ашиглаж байна:
- `app/(admin)/notify/page.tsx` — admin мэдэгдэл **бичиж илгээх** хуудас (`SEED_SENT`)
- `app/(admin)/layout.tsx` — толгой хэсгийн 🔔 дуут дохионы **хүлээн авсан мэдэгдлийн** жагсаалт
  (`TEST_NOTIFICATIONS`, unread badge)

Эдгээр хоёулаа **нэг** backend модулиар (`notifications` + fan-out) ажиллана — admin илгээхэд,
тухайн хэрэглэгч бүр өөрийн inbox-даа хүлээж авна.

Зураг хавсаргах нь аль хэдийн бодит `POST /api/upload`-аар ажиллаж байгаа тул энэ спекд
шинэ upload endpoint шаардлагагүй.

## 2. Өгөгдлийн бүтэц

### notifications

```sql
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,

    title VARCHAR(300) NOT NULL,
    body TEXT NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'info',   -- 'info' | 'reminder' | 'urgent'
    image_url TEXT NULL,

    audience_type VARCHAR(20) NOT NULL,          -- 'all' | 'role' | 'picked'
    role_id BIGINT NULL,                         -- audience_type='role' үед

    status VARCHAR(20) NOT NULL DEFAULT 'draft',  -- 'draft' | 'scheduled' | 'sent'
    scheduled_at TIMESTAMP NULL,
    sent_at TIMESTAMP NULL,

    created_by BIGINT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### notification_recipients (fan-out + уншсан эсэх)

```sql
CREATE TABLE notification_recipients (
    id BIGSERIAL PRIMARY KEY,
    notification_id BIGINT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (notification_id, user_id)
);
```

Илгээх (send) хийх мөчид `audience_type`-аар тодорхойлогдох хэрэглэгч бүрт нэг мөр
үүснэ: `all` → бүх идэвхтэй хэрэглэгч, `role` → `role_id`-тай тэнцэх хэрэглэгчид, `picked` →
`POST`-д ирсэн `user_ids` жагсаалт.

## 3. Admin API (илгээх талд)

```http
GET /api/admin/notifications
```
Query: `status`, `type`, `search`, `page`, `per_page`.
```json
{
  "items": [
    {
      "id": 4, "title": "Гишүүнчлэлийн хураамж сануулга", "type": "reminder", "image_url": null,
      "audience_type": "role", "role_name": "БЗД хороо",
      "status": "sent", "sent_at": "2026-06-18 09:00:00",
      "recipient_count": 742, "read_count": 631
    }
  ],
  "page": 1, "pages": 1, "per_page": 20, "total": 1
}
```
`role_name`, `recipient_count`, `read_count` — денормалчилсан/тооцоолсон талбарууд (одоогийн
`/organization`-ийн `school_category_name` гэх мэттэй адил хэв маяг).

```http
POST /api/admin/notifications
```
```json
{
  "audience_type": "role",
  "role_id": 3,
  "type": "reminder",
  "title": "Гишүүнчлэлийн хураамж сануулга",
  "body": "...",
  "image_url": "https://.../uploads/2026/09/banner.jpg",
  "scheduled_at": null
}
```
- `audience_type="picked"` үед `"user_ids": [12, 15, 20]` талбар нэмж явуулна.
- `scheduled_at` өгөөгүй (`null`) бол шууд `status=sent`, `sent_at=NOW()` болж fan-out хийгдэнэ.
- `scheduled_at` өгвөл `status=scheduled` болно; тухайн цагт хүрэхэд `sent`-рүү шилжиж
  fan-out хийх cron/job хэрэгтэй (доор §5-д дурдсан).

```http
DELETE /api/admin/notifications/{id}
```
Зөвхөн `draft`/`scheduled` төлөвтэй мэдэгдлийг л устгах/цуцлах боломжтой (`sent`-г
буцаана уу гэвэл 422).

## 4. Хэрэглэгчийн өөрийн inbox (🔔 дуут дохио)

```http
GET /api/notifications?unread=1
```
```json
{
  "unread_count": 2,
  "items": [
    { "id": 4, "title": "Гишүүнчлэлийн хураамж сануулга", "body": "...", "type": "reminder", "image_url": null, "created_at": "2026-06-18 09:00:00", "read_at": null }
  ]
}
```

```http
POST /api/notifications/{id}/read
```
Тухайн хэрэглэгчийн `notification_recipients.read_at`-г `NOW()` болгоно. Хариу: `{ "status": true }`.

## 5. Хэрэгжүүлэх дараалал

1. **Migration** — `notifications`, `notification_recipients`
2. **`POST /api/admin/notifications`** — fan-out логик (`audience_type`-аар хэрэглэгчид тодорхойлж
   `notification_recipients` мөрүүд үүсгэх)
3. **`GET /api/admin/notifications`** — жагсаалт + `recipient_count`/`read_count` тооцоолол
4. **`GET /api/notifications`, `POST /api/notifications/{id}/read`** — хэрэглэгчийн inbox
5. **Scheduled job** — `scheduled_at <= NOW()` бөгөөд `status='scheduled'` мэдэгдлүүдийг
   тогтмол (жишээ нь 1 минут тутам) шалгаж fan-out хийж `sent` болгох
6. **Frontend** — `app/(admin)/notify/page.tsx`-ийн `SEED_SENT`-г §3-ын жагсаалтаар,
   `app/(admin)/layout.tsx`-ийн `TEST_NOTIFICATIONS`/`unreadCount`-г §4-ийн inbox-оор сольно
   (Зураг байршуулалт аль хэдийн бодит тул өөрчлөлт хэрэггүй)
