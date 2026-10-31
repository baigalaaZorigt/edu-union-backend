"""Нүүр хуудасны «Холбооны тухай» — admin/home_about.py + client/home.py (/api/portal/home_about)."""
import pytest

BASE = "/api/admin/home_about"


@pytest.fixture
def restore(api):
    """Тестийн өмнөх title/body ба картуудын төлөвийг буцааж тавина (DB session-д хуваалцдаг)."""
    before = api.get(BASE).get_json()
    seed_ids = {c["id"] for c in before["cards"]}
    yield before
    api.put(BASE, json={"title": before["title"], "body": before["body"]})
    for c in api.get(BASE).get_json()["cards"]:
        if c["id"] not in seed_ids:
            api.delete(f"{BASE}/cards/{c['id']}")
    for c in before["cards"]:
        api.put(f"{BASE}/cards/{c['id']}", json={"title": c["title"], "text": c["text"],
                                                  "is_visible": c["is_visible"]})
    api.put(f"{BASE}/cards/reorder", json={"ids": [c["id"] for c in before["cards"]]})


def test_seeded_public_shape(anon):
    r = anon.get("/api/portal/home_about")
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "public, max-age=300"
    d = r.get_json()
    assert d["title"] == "Холбооны тухай"
    assert len(d["body"].split("\n\n")) == 2
    assert [c["title"] for c in d["cards"]] == ["Алсын хараа", "Эрхэм зорилго",
                                                "Үйл ажиллагааны зарчим"]
    assert set(d["cards"][0]) == {"id", "title", "text"}
    assert d["updated_at"].endswith("Z")


def test_admin_needs_token(anon):
    assert anon.get(BASE).status_code == 401
    assert anon.post(f"{BASE}/cards", json={"title": "a", "text": "b"}).status_code == 401


def test_admin_permission(make_user):
    reader, _ = make_user(["home_about.read"])
    assert reader.get(BASE).status_code == 200
    assert reader.put(BASE, json={"title": "x"}).status_code == 403
    assert reader.put(f"{BASE}/cards/reorder", json={"ids": []}).status_code == 403


def test_update_section_cleans_text(api, anon, restore):
    r = api.put(BASE, json={"title": "  <b>Бидний</b> тухай ",
                            "body": "Нэг <script>x</script>догол\r\n  \n\n\n\nХоёр  "})
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["title"] == "Бидний тухай"
    assert d["body"] == "Нэг xдогол\n\nХоёр"
    assert anon.get("/api/portal/home_about").get_json()["body"] == "Нэг xдогол\n\nХоёр"
    # PATCH хэсэгчилсэн — body хөндөгдөхгүй
    assert api.patch(BASE, json={"title": "Т"}).get_json()["body"] == "Нэг xдогол\n\nХоёр"


@pytest.mark.parametrize("body, field", [
    ({"title": ""}, "title"),
    ({"title": "x" * 121}, "title"),
    ({"body": "x" * 1501}, "body"),
    ({"body": 5}, "body"),
])
def test_update_section_422(api, body, field):
    r = api.put(BASE, json=body)
    assert r.status_code == 422
    assert field in r.get_json()["errors"]


def test_card_crud_hide_reorder(api, anon, restore):
    seed = [c["id"] for c in restore["cards"]]
    r = api.post(f"{BASE}/cards", json={"title": "Үнэт зүйл", "text": "<i>Эв</i> нэгдэл"})
    assert r.status_code == 201, r.get_json()
    card = r.get_json()
    assert card["text"] == "Эв нэгдэл" and card["is_visible"] is True
    assert card["sort_order"] > max(c["sort_order"] for c in restore["cards"])
    cid = card["id"]

    public = lambda: [c["id"] for c in anon.get("/api/portal/home_about").get_json()["cards"]]  # noqa: E731
    assert public() == seed + [cid]

    # нуух -> порталд алга, админд байна
    assert api.patch(f"{BASE}/cards/{cid}", json={"is_visible": False}).status_code == 200
    assert cid not in public()
    assert cid in [c["id"] for c in api.get(BASE).get_json()["cards"]]
    assert api.put(f"{BASE}/cards/{cid}", json={"is_visible": True}).status_code == 200

    # дараалал
    order = [cid] + seed[::-1]
    r = api.put(f"{BASE}/cards/reorder", json={"ids": order})
    assert r.status_code == 200, r.get_json()
    assert [c["id"] for c in r.get_json()["cards"]] == order
    assert public() == order
    # дутуу / давхар / буруу id -> 422
    for bad in ([cid], order + [cid], order[:-1] + [999999], "1,2", [True]):
        assert api.put(f"{BASE}/cards/reorder", json={"ids": bad}).status_code == 422

    # засах — хэсэгчилсэн, буруу утга 422
    assert api.put(f"{BASE}/cards/{cid}", json={"text": "Шинэ"}).get_json()["title"] == "Үнэт зүйл"
    r = api.put(f"{BASE}/cards/{cid}", json={"title": "", "text": "x" * 301})
    assert r.status_code == 422 and set(r.get_json()["errors"]) == {"title", "text"}

    assert api.delete(f"{BASE}/cards/{cid}").get_json() == {"deleted": cid}
    assert api.delete(f"{BASE}/cards/{cid}").status_code == 404
    assert cid not in public()


def test_card_limits(api, anon, restore):
    assert api.post(f"{BASE}/cards", json={"title": "x"}).status_code == 422
    n = len(restore["cards"])
    for i in range(6 - n):
        assert api.post(f"{BASE}/cards", json={"title": f"К{i}", "text": "т"}).status_code == 201
    r = api.post(f"{BASE}/cards", json={"title": "илүү", "text": "т"})
    assert r.status_code == 422 and "cards" in r.get_json()["errors"]
    # порталд дээд тал нь 4
    assert len(anon.get("/api/portal/home_about").get_json()["cards"]) == 4


def test_empty_configuration(api, anon, restore):
    for c in restore["cards"]:
        api.patch(f"{BASE}/cards/{c['id']}", json={"is_visible": False})
    api.put(BASE, json={"body": ""})
    r = anon.get("/api/portal/home_about")
    assert r.status_code == 200
    d = r.get_json()
    assert d["body"] == "" and d["cards"] == []
