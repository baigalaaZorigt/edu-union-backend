"""Хуваарьт мэдэгдлүүдийг илгээх скрипт (cron / systemd timer дуудна).

    python scripts/send_due_notifications.py

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
                python scripts/send_due_notifications.py

Cron байхгүй ч хуваарьт мэдэгдэл гээгдэхгүй: админы жагсаалт болон хэрэглэгчийн
inbox уншигдах үед `dispatch_due()` мөн дуудагдана. Админы layout-ийн 🔔 нь хуудас
бүр inbox-оо татдаг тул практикт хоцролт бага — гэхдээ хэн ч систем нээхгүй бол
хүлээнэ.
"""
import os
import sys

# `python scripts/<нэр>.py` гэж ажиллуулахад repo-ийн үндэс sys.path-д байхгүй тул нэмнэ.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.orm as orm  # noqa: E402
from admin.notifications import dispatch_due  # noqa: E402

if __name__ == "__main__":
    s = orm.new_session()
    try:
        sent = dispatch_due(s)
    finally:
        s.close()
        orm.dispose()
    print(f"Илгээсэн хуваарьт мэдэгдэл: {sent}")
