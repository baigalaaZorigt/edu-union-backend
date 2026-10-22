"""Эрх зүй (legal_reference) — нэмэлт талбарууд (0009): дугаар, огноо, товч утга, PDF."""
import os

from _content_helpers import _disk_path, _upload
from conftest import PDF_BYTES, uniq

URL = "/api/legal_reference"
FIELDS = ("doc_number", "approved_date", "summary", "pdf_url", "pdf_name")


def _pdf(api):
    r = _upload(api, name="boloworol.pdf", data=PDF_BYTES)
    assert r.status_code in (200, 201), r.get_json()
    return r.get_json()


def test_upload_accepts_pdf_and_serves_it_token_free(api, anon):
    up = _pdf(api)
    assert up["url"].startswith("/uploads/content/") and up["url"].endswith(".pdf")
    assert up["name"] == "boloworol.pdf" and up["mime_type"] == "application/pdf"
    r = anon.get(up["url"])
    assert r.status_code == 200 and r.data.startswith(b"%PDF-")


def test_fields_round_trip_admin_and_portal(api, anon):
    up = _pdf(api)
    body = {"title": uniq("Хууль"), "doc_number": " № 123 ", "approved_date": "2026-05-12",
            "summary": "Боловсролын системийн үндсэн зарчим.", "pdf_url": up["url"],
            "pdf_name": up["name"]}
    r = api.post(URL, json=body)
    assert r.status_code == 201, r.get_json()
    row = r.get_json()
    assert row["doc_number"] == "№ 123" and row["approved_date"] == "2026-05-12"
    assert (row["pdf_url"], row["pdf_name"]) == (up["url"], "boloworol.pdf")
    items = {i["id"]: i for i in anon.get("/api/portal/legal_references").get_json()["items"]}
    assert all(items[row["id"]][f] == row[f] for f in FIELDS)
    api.delete(f"{URL}/{row['id']}")


def test_optional_and_blank_becomes_null(api):
    row = api.post(URL, json={"title": uniq("Хууль")}).get_json()
    assert all(row[f] is None for f in FIELDS)
    r = api.patch(f"{URL}/{row['id']}", json={"doc_number": "№ 1", "summary": "x"})
    assert r.get_json()["doc_number"] == "№ 1"
    r = api.patch(f"{URL}/{row['id']}", json={"doc_number": "  ", "summary": "",
                                              "approved_date": ""})
    d = r.get_json()
    assert d["doc_number"] is None and d["summary"] is None and d["approved_date"] is None
    api.delete(f"{URL}/{row['id']}")


def test_validation(api):
    t = uniq("Хууль")
    for bad in ({"approved_date": "2026.05.12"}, {"approved_date": "2026-02-30"},
                {"approved_date": "2026-5-1"}, {"approved_date": 20260512},
                {"doc_number": "1" * 101}, {"summary": "x" * 5001}, {"pdf_name": "a" * 256},
                {"pdf_url": "https://evil.example/a.pdf"}, {"pdf_url": "/uploads/content/a.png"},
                {"pdf_url": "/uploads/content/../x.pdf"}, {"pdf_url": "/uploads/form/a.pdf"}):
        assert api.post(URL, json={"title": t, **bad}).status_code == 400, bad
    assert api.post(URL, json={"title": t, "doc_number": "1" * 100}).status_code == 201


def test_replaced_pdf_leaves_storage_deleted_row_keeps_it(api, anon):
    first, second = _pdf(api), _pdf(api)
    row = api.post(URL, json={"title": uniq("Хууль"), "pdf_url": first["url"],
                              "pdf_name": "a.pdf"}).get_json()
    r = api.put(f"{URL}/{row['id']}", json={"pdf_url": second["url"], "pdf_name": "b.pdf"})
    assert r.status_code == 200
    assert not os.path.exists(_disk_path(first["url"]))
    r = api.patch(f"{URL}/{row['id']}", json={"pdf_url": None})       # PDF-ийг авах
    assert r.get_json()["pdf_url"] is None and r.get_json()["pdf_name"] is None
    assert not os.path.exists(_disk_path(second["url"]))
    third = _pdf(api)
    api.patch(f"{URL}/{row['id']}", json={"pdf_url": third["url"], "title": "Шинэ"})
    assert api.delete(f"{URL}/{row['id']}").status_code == 200
    assert anon.get(third["url"]).status_code == 200                  # soft delete — файл үлдэнэ


def test_search_finds_pdf_row_by_summary(api, anon):
    up = _pdf(api)
    word = uniq("Зарчимтест")
    row = api.post(URL, json={"title": uniq("Хууль"), "pdf_url": up["url"],
                              "summary": f"{word} тайлбар"}).get_json()
    r = anon.get("/api/portal/search", query_string={"q": word})
    hits = [i for i in r.get_json().get("items", []) if i["id"] == row["id"]]
    assert hits and hits[0]["type"] == "document" and hits[0]["path"] == up["url"]
    api.delete(f"{URL}/{row['id']}")
