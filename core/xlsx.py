"""Excel (.xlsx) экспорт — хуваалцсан бичигч.

`xlsx_response(name, sheets)` нь нэг буюу хэд хэдэн хуудастай файл үүсгээд татаж авах
хариу болгон буцаана:
  * 1-р мөр — монгол толгой, тод (bold), хөлдөөсөн (freeze_panes)
  * None -> хоосон нүд ("null" биш); datetime.date -> жинхэнэ огноо нүд (yyyy-mm-dd)
  * баганын өргөнийг агуулгаар (дээд тал 60)
  * xlsxwriter-ийн `constant_memory` горим — мөр бүр бичигдмэгц түр файл руу гарна,
    бүх workbook санах ойд хуримтлагдахгүй (олон мянган мөрөнд ч). Түр файлыг нээмэгц
    нэрийг нь устгадаг тул серверт юу ч үлдэхгүй.
Нэр: `<name>-YYYY-MM-DD.xlsx` (кирилл нэр ч болно — send_file RFC 5987-оор кодлоно).
"""
import datetime as dt
import os
import tempfile

from flask import send_file

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_WIDTH = 60


class Sheet:
    """Нэг хуудас: гарчиг, баганын толгойнууд, мөрүүдийг гаргах iterable."""

    def __init__(self, title, headers, rows):
        self.title = title[:31]                       # Excel хуудасны нэрийн хязгаар
        self.headers = headers
        self.rows = rows


def _width(value):
    if value is None:
        return 0
    if isinstance(value, dt.datetime):
        return 16
    if isinstance(value, dt.date):
        return 10
    return min(MAX_WIDTH, max(len(line) for line in str(value).split("\n")) if str(value) else 0)


def _write_sheet(wb, sheet, bold, date_fmt, dt_fmt):
    ws = wb.add_worksheet(sheet.title)
    widths = [len(h) for h in sheet.headers]
    for c, h in enumerate(sheet.headers):
        ws.write_string(0, c, h, bold)
    ws.freeze_panes(1, 0)
    r = 0
    for r, row in enumerate(sheet.rows, start=1):
        for c, value in enumerate(row):
            if value is None or value == "":
                continue                              # хоосон нүд
            if isinstance(value, dt.datetime):
                ws.write_datetime(r, c, value, dt_fmt)
            elif isinstance(value, dt.date):
                ws.write_datetime(r, c, dt.datetime(value.year, value.month, value.day), date_fmt)
            elif isinstance(value, bool):
                ws.write_boolean(r, c, value)
            elif isinstance(value, (int, float)):
                ws.write_number(r, c, value)
            else:
                ws.write_string(r, c, str(value))
            widths[c] = max(widths[c], _width(value))
    for c, w in enumerate(widths):
        ws.set_column(c, c, min(MAX_WIDTH, w + 2))
    return r


def xlsx_response(name, sheets):
    """Хуудсуудыг .xlsx болгож attachment хариу буцаана."""
    import xlsxwriter
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    try:
        wb = xlsxwriter.Workbook(path, {"constant_memory": True})
        bold = wb.add_format({"bold": True})
        date_fmt = wb.add_format({"num_format": "yyyy-mm-dd"})
        dt_fmt = wb.add_format({"num_format": "yyyy-mm-dd hh:mm"})
        for sheet in sheets:
            _write_sheet(wb, sheet, bold, date_fmt, dt_fmt)
        wb.close()
    except Exception:
        os.unlink(path)
        raise
    # Нээгээд ШУУД unlink: нээлттэй handle-аар уншигдсаар байх ч нэр нь дискнээс алга —
    # хариу дуусаж handle хаагдмагц зай чөлөөлөгдөнө (close hook-оос хамааралгүй, үлдэхгүй).
    fh = open(path, "rb")
    os.unlink(path)
    return send_file(fh, mimetype=MIME, as_attachment=True,
                     download_name=f"{name}-{dt.date.today().isoformat()}.xlsx")


def as_datetime(value):
    """'YYYY-MM-DD HH:MM[:SS]' (эсвэл ISO) -> datetime.datetime (буруу/хоосон бол None)."""
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "")[:19])
    except ValueError:
        return None


def as_date(value):
    """'YYYY-MM-DD...' -> datetime.date (буруу/хоосон бол None)."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None
