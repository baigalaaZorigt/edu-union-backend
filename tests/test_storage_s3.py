"""core/storage.py — S3 горим (moto-гоор хуурамч S3). Аппын сервер дээр файл үлдэхгүйг шалгана."""
import io
import os

import boto3
import pytest
from moto import mock_aws

import admin.content as content
import admin.union.common as union_common
import core.storage as storage
from core.forms_core import UPLOAD_DIR as FORM_DIR
from conftest import uniq, PDF_BYTES, PNG_BYTES

BUCKET = "edu-union-test-uploads"


@pytest.fixture
def s3(monkeypatch):
    with mock_aws():
        client = boto3.client("s3", region_name="ap-northeast-1")
        client.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={
            "LocationConstraint": "ap-northeast-1"})
        monkeypatch.setattr(storage, "S3_BUCKET", BUCKET)
        monkeypatch.setattr(storage, "_client", client)
        yield client


def _keys(client, prefix="uploads/"):
    resp = client.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
    return {o["Key"] for o in resp.get("Contents", [])}


def _local_files(folder):
    return {os.path.join(r, f) for r, _, fs in os.walk(folder) for f in fs} \
        if os.path.isdir(folder) else set()


def test_content_upload_serve_delete(api, anon, s3):
    before = _local_files(content.UPLOAD_DIR)
    r = api.post("/api/upload", data={"file": (io.BytesIO(PNG_BYTES), "a.png")},
                 content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    url = r.get_json()["url"]
    key = "uploads/content/" + os.path.basename(url)
    assert key in _keys(s3)
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    assert obj["ContentType"] == "image/png"
    assert _local_files(content.UPLOAD_DIR) == before          # дискэнд юу ч бичигдээгүй

    got = anon.get(url)                                         # токенгүй, S3-аас уншина
    assert got.status_code == 200 and got.data == PNG_BYTES
    assert got.mimetype == "image/png"
    assert anon.get("/uploads/content/nope.png").status_code == 404

    # баннер устгахад мөр нуугдана — S3-ийн объект үлдэнэ (soft delete)
    bid = api.post("/api/banner", json={"image_url": url}).get_json()["id"]
    assert api.delete(f"/api/banner/{bid}").status_code == 200
    assert key in _keys(s3)                # soft delete — объект үлдэнэ


def test_member_file_s3(api, s3):
    org = api.post("/api/organization", json={
        "name": uniq("S3 сургууль"), "org_code": f"{int(uniq('')) % 900 + 100:03d}"}).get_json()
    mem = api.post("/api/member", json={"organization_id": org["id"], "last_name": "S3",
                                        "first_name": "Гишүүн"}).get_json()
    before = _local_files(union_common.UPLOAD_DIR)
    r = api.post("/api/member_file", data={
        "member_id": str(mem["id"]),
        "file": [(io.BytesIO(PDF_BYTES), "батламж.pdf"), (io.BytesIO(PDF_BYTES), "b.pdf")]},
        content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    files = r.get_json()
    keys = {f"uploads/member/{f['stored_name']}" for f in files}
    assert keys <= _keys(s3)
    assert _local_files(union_common.UPLOAD_DIR) == before

    d = api.get(f"/api/member_file/{files[0]['id']}/download")
    assert d.status_code == 200 and d.data == PDF_BYTES
    assert "attachment" in d.headers["Content-Disposition"]
    assert "filename*=UTF-8''" in d.headers["Content-Disposition"]   # кирилл нэр

    assert api.delete(f"/api/member_file/{files[0]['id']}").status_code == 200
    assert f"uploads/member/{files[0]['stored_name']}" in _keys(s3)
    # soft delete: байгууллага устгахад (каскад) мөр нуугдана, S3-ийн объект үлдэнэ
    assert api.delete(f"/api/organization/{org['id']}").status_code == 200
    assert keys <= _keys(s3)


def test_member_file_missing_object(api, s3):
    org = api.post("/api/organization", json={
        "name": uniq("S3 сургууль"), "org_code": f"{int(uniq('')) % 900 + 100:03d}"}).get_json()
    mem = api.post("/api/member", json={"organization_id": org["id"], "last_name": "S3",
                                        "first_name": "Алга"}).get_json()
    f = api.post("/api/member_file", data={"member_id": str(mem["id"]),
                                           "file": (io.BytesIO(PDF_BYTES), "x.pdf")},
                 content_type="multipart/form-data").get_json()[0]
    s3.delete_object(Bucket=BUCKET, Key=f"uploads/member/{f['stored_name']}")
    assert api.get(f"/api/member_file/{f['id']}/download").status_code == 404
    api.delete(f"/api/organization/{org['id']}")


def test_form_document_s3(api, anon, s3):
    fid = api.post("/api/admin/forms", json={"title": uniq("S3 poll"), "type": "poll"}).get_json()["id"]
    before = _local_files(FORM_DIR)
    r = api.post(f"/api/admin/forms/{fid}/document",
                 data={"file": (io.BytesIO(PDF_BYTES), "p.pdf")}, content_type="multipart/form-data")
    assert r.status_code == 201, r.get_json()
    doc = r.get_json()[0]
    path = doc.get("file_path") or doc.get("url")
    key = "uploads/form/" + os.path.basename(path)
    assert key in _keys(s3) and _local_files(FORM_DIR) == before
    got = anon.get(path)
    assert got.status_code == 200 and got.data == PDF_BYTES and got.mimetype == "application/pdf"
    assert api.delete(f"/api/admin/documents/{doc['id']}").status_code == 200
    assert key in _keys(s3)
    api.delete(f"/api/admin/forms/{fid}?hard=1")
