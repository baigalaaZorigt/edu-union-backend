"""Эрх зүй — дугаарласан мод (legal_reference): CRUD, каскад устгал, эрэмбэ, портал."""
import pytest

from conftest import uniq

URL = "/api/legal_reference"


def _new(api, **body):
    r = api.post(URL, json={"title": uniq("Хууль"), **body})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


@pytest.fixture
def tree(api):
    """1 хэсэг -> 2 мөр (нэг нь холбоостой) -> 1 дэд мөр."""
    top = _new(api)
    a = _new(api, parent_id=top["id"], url="https://legalinfo.mn/a")
    b = _new(api, parent_id=top["id"])
    leaf = _new(api, parent_id=b["id"], url="https://legalinfo.mn/leaf")
    yield top, a, b, leaf
    api.delete(f"{URL}/{top['id']}")


def _portal(anon):
    r = anon.get("/api/portal/legal_references")
    assert r.status_code == 200
    return {i["id"]: i for i in r.get_json()["items"]}


def test_create_read_shape(api, tree):
    top, a, b, leaf = tree
    assert top["parent_id"] is None and top["url"] is None and top["is_visible"] is True
    assert top["created_by"] == 1 and "deleted_at" not in top
    assert (a["sort_order"], b["sort_order"]) == (1, 2)          # ах дүүсийн төгсгөлд нэмэгдэнэ
    assert leaf["parent_id"] == b["id"] and leaf["sort_order"] == 1
    ids = [r["id"] for r in api.get(URL).get_json()]
    assert {top["id"], a["id"], b["id"], leaf["id"]} <= set(ids)
    assert api.get(f"{URL}/{leaf['id']}").get_json()["url"] == "https://legalinfo.mn/leaf"


def test_validation(api, tree):
    top, a, b, leaf = tree
    assert api.post(URL, json={"title": "  "}).status_code == 400
    assert api.post(URL, json={"title": "x", "url": "javascript:alert(1)"}).status_code == 400
    assert api.post(URL, json={"title": "x", "parent_id": 99999999}).status_code == 400
    # цикл: мөр өөрөө / өөрийн удам эцэг болохгүй
    assert api.put(f"{URL}/{top['id']}", json={"parent_id": top["id"]}).status_code == 400
    assert api.patch(f"{URL}/{top['id']}", json={"parent_id": leaf["id"]}).status_code == 400
    assert api.put(f"{URL}/{a['id']}", json={}).status_code == 400
    assert api.get(f"{URL}/99999999").status_code == 404


def test_update_and_move(api, tree):
    top, a, b, leaf = tree
    r = api.patch(f"{URL}/{leaf['id']}", json={"parent_id": None, "url": "", "title": " Шинэ "})
    assert r.status_code == 200
    d = r.get_json()
    assert d["parent_id"] is None and d["url"] is None and d["title"] == "Шинэ"
    assert d["updated_by"] == 1
    api.patch(f"{URL}/{leaf['id']}", json={"parent_id": b["id"]})


def test_reorder_siblings(api, tree):
    top, a, b, leaf = tree
    r = api.put(f"{URL}/reorder", json={"items": [{"id": b["id"], "sort_order": 1},
                                                  {"id": a["id"], "sort_order": 2}]})
    assert r.status_code == 200 and [x["id"] for x in r.get_json()] == [b["id"], a["id"]]
    assert api.get(f"{URL}/{a['id']}").get_json()["sort_order"] == 2
    mixed = {"items": [{"id": a["id"], "sort_order": 1}, {"id": leaf["id"], "sort_order": 2}]}
    assert api.patch(f"{URL}/reorder", json=mixed).status_code == 400      # өөр эцэгтэй
    assert api.put(f"{URL}/reorder", json={"items": []}).status_code == 400
    assert api.put(f"{URL}/reorder", json={"items": [{"id": 99999999, "sort_order": 1}]}
                   ).status_code == 404


def test_portal_hides_whole_subtree(api, anon, tree):
    top, a, b, leaf = tree
    shown = _portal(anon)
    assert set(shown[leaf["id"]]) == {"id", "parent_id", "title", "url", "sort_order"}
    assert {top["id"], a["id"], b["id"], leaf["id"]} <= set(shown)
    api.patch(f"{URL}/{b['id']}", json={"is_visible": False})
    shown = _portal(anon)
    assert b["id"] not in shown and leaf["id"] not in shown and a["id"] in shown
    api.patch(f"{URL}/{top['id']}", json={"is_visible": False})
    assert not {top["id"], a["id"], b["id"], leaf["id"]} & set(_portal(anon))


def test_delete_cascades_subtree(api, anon):
    top = _new(api)
    child = _new(api, parent_id=top["id"])
    leaf = _new(api, parent_id=child["id"])
    assert api.delete(f"{URL}/{top['id']}").status_code == 200
    for row in (top, child, leaf):
        assert api.get(f"{URL}/{row['id']}").status_code == 404
    assert api.delete(f"{URL}/{top['id']}").status_code == 404


def test_permissions(anon, make_user):
    assert anon.get(URL).status_code == 401
    u, _ = make_user(["legal_reference.read"])
    assert u.get(URL).status_code == 200
    assert u.post(URL, json={"title": "x"}).status_code == 403
    assert u.put(f"{URL}/reorder", json={"items": []}).status_code == 403
