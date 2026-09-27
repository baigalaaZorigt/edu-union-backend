"""admin/union/ — horoo / organization / member / contact / member_file — member_file."""

import io
import os

import pytest

import admin.union.common as union
import admin.union.member_file as member_file
from conftest import PDF_BYTES, PNG_BYTES

from _union_helpers import make_member, make_org, upload


# ============================ member_file ============================
@pytest.fixture
def member(api):
    o = make_org(api)
    m = make_member(api, o["id"])
    yield m
    api.delete(f"/api/organization/{o['id']}")


def test_member_file_flow(api, member):
    r = upload(api, member["id"], [("батламж.pdf", PDF_BYTES), ("b.PDF", PDF_BYTES)],
               note="анхны")
    assert r.status_code == 201
    files = r.get_json()
    assert len(files) == 2
    f = files[0]
    assert f["file_name"] == "батламж.pdf" and f["size"] == len(PDF_BYTES)
    assert f["note"] == "анхны" and f["member_id"] == member["id"]
    assert os.path.isfile(os.path.join(union.UPLOAD_DIR, f["stored_name"]))

    lst = api.get(f"/api/member_file?member_id={member['id']}").get_json()
    assert [x["id"] for x in lst] == [x["id"] for x in files]
    assert any(x["id"] == f["id"] for x in api.get("/api/member_file").get_json())
    assert api.get(f"/api/member_file/{f['id']}").get_json()["stored_name"] == f["stored_name"]

    r = api.get(f"/api/member_file/{f['id']}/download")
    assert r.status_code == 200
    assert r.mimetype == "application/pdf" and r.data == PDF_BYTES
    assert "attachment" in r.headers["Content-Disposition"]

    r = api.put(f"/api/member_file/{f['id']}", json={"note": "PUT"})
    assert r.status_code == 200 and r.get_json()["fields"] == ["note"]
    assert api.patch(f"/api/member_file/{f['id']}", json={"note": "PATCH"}).status_code == 200
    assert api.get(f"/api/member_file/{f['id']}").get_json()["note"] == "PATCH"

    assert len(api.get(f"/api/member/{member['id']}").get_json()["files"]) == 2

    path = os.path.join(union.UPLOAD_DIR, f["stored_name"])
    assert api.delete(f"/api/member_file/{f['id']}").status_code == 200
    assert os.path.exists(path)                            # soft delete — файл үлдэнэ
    assert api.get(f"/api/member_file/{f['id']}").status_code == 404
    assert api.get(f"/api/member_file/{f['id']}/download").status_code == 404
    # нөгөө файл хэвээр
    assert os.path.isfile(os.path.join(union.UPLOAD_DIR, files[1]["stored_name"]))


def test_member_file_files_field_alias(api, member):
    data = {"member_id": str(member["id"]), "files": (io.BytesIO(PDF_BYTES), "c.pdf")}
    r = api.post("/api/member_file", data=data, content_type="multipart/form-data")
    assert r.status_code == 201 and len(r.get_json()) == 1


@pytest.mark.parametrize("name,content", [
    ("image.png", PNG_BYTES),               # PDF биш өргөтгөл
    ("fake.pdf", PNG_BYTES),                # %PDF- толгойгүй
    ("empty.pdf", b""),                     # хоосон
])
def test_member_file_rejects(api, member, name, content):
    before = len(os.listdir(union.UPLOAD_DIR)) if os.path.isdir(union.UPLOAD_DIR) else 0
    r = upload(api, member["id"], [("ok.pdf", PDF_BYTES), (name, content)])
    assert r.status_code == 400
    # нэг нь буруу бол НЭГ Ч файл хадгалагдахгүй
    assert api.get(f"/api/member_file?member_id={member['id']}").get_json() == []
    after = len(os.listdir(union.UPLOAD_DIR)) if os.path.isdir(union.UPLOAD_DIR) else 0
    assert after == before


def test_member_file_too_big(api, member, monkeypatch):
    monkeypatch.setattr(member_file, "MAX_FILE_SIZE", 10)
    assert upload(api, member["id"], [("a.pdf", PDF_BYTES)]).status_code == 400


def test_member_file_errors(api, member):
    assert api.post("/api/member_file", data={"file": (io.BytesIO(PDF_BYTES), "a.pdf")},
                    content_type="multipart/form-data").status_code == 400
    assert api.post("/api/member_file", data={"member_id": "abc",
                                              "file": (io.BytesIO(PDF_BYTES), "a.pdf")},
                    content_type="multipart/form-data").status_code == 400
    assert api.post("/api/member_file", data={"member_id": str(member["id"])},
                    content_type="multipart/form-data").status_code == 400
    assert upload(api, 999999, [("a.pdf", PDF_BYTES)]).status_code == 400
    assert api.post("/api/member_file", json={"member_id": member["id"]}).status_code == 400
    assert api.get("/api/member_file/999999").status_code == 404
    assert api.get("/api/member_file/999999/download").status_code == 404
    assert api.put("/api/member_file/999999", json={"note": "x"}).status_code == 404
    assert api.delete("/api/member_file/999999").status_code == 404
    f = upload(api, member["id"], [("a.pdf", PDF_BYTES)]).get_json()[0]
    assert api.patch(f"/api/member_file/{f['id']}", json={"x": 1}).status_code == 400


def test_member_file_download_missing_on_disk(api, member):
    f = upload(api, member["id"], [("a.pdf", PDF_BYTES)]).get_json()[0]
    os.remove(os.path.join(union.UPLOAD_DIR, f["stored_name"]))
    assert api.get(f"/api/member_file/{f['id']}/download").status_code == 404
