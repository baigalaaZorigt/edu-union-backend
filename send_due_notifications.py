"""Хуваарьт мэдэгдлүүдийг илгээх скрипт (cron / systemd timer дуудна).

    python send_due_notifications.py

`scheduled_at` хүрсэн бөгөөд `status='scheduled'` мэдэгдэл бүрийг fan-out хийж
`sent` болгоно (notification_api_spec.md §5). Хэд ч удаа, зэрэг ажиллуулахад
аюулгүй: `notification_recipients` нь UNIQUE(notification_id, user_id)-аар
хамгаалагдсан, төлөв солих нь `status='scheduled'` нөхцөлтэй.

**Одоогоор энэ скриптийг cron-д ТОХИРУУЛААГҮЙ** (2026-09-17-ны шийдвэр) — хуваарьт
мэдэгдэл нь доорх "залхуу" замаар илгээгддэг. Хэрэв нэг минутын нарийвчлалтай
илгээх шаардлага гарвал энд байгаа жишээгээр тохируулна.

Жишээ crontab (минут тутам):

    * * * * * cd /opt/edu-union/app && /usr/bin/python3 send_due_notifications.py

Docker дээр:

    * * * * * cd /opt/edu-union && docker compose run --rm --no-deps app \\
                python send_due_notifications.py

Cron байхгүй ч хуваарьт мэдэгдэл гээгдэхгүй: админы жагсаалт болон хэрэглэгчийн
inbox уншигдах үед `dispatch_due()` мөн дуудагдана. Админы layout-ийн 🔔 нь хуудас
бүр inbox-оо татдаг тул практикт хоцролт бага — гэхдээ хэн ч систем нээхгүй бол
хүлээнэ.
"""
from db import get_db
from admin.notifications import dispatch_due

if __name__ == "__main__":
    conn = get_db()
    try:
        sent = dispatch_due(conn)
    finally:
        conn.close()
    print(f"Илгээсэн хуваарьт мэдэгдэл: {sent}")
