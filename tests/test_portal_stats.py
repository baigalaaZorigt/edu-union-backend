"""GET /api/portal/membership_structure — «Гишүүнчлэлийн бүтэц» (токенгүй)."""
from client.stats import percents
from conftest import MEMBER_REQ, uniq

URL = "/api/portal/membership_structure"


def _org(api, category=None):
    body = {"name": uniq("Статистик сургууль"), "org_code": f"{int(uniq('')) % 900 + 100:03d}"}
    if category:
        body["school_category_id"] = category
    r = api.post("/api/organization", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _members(api, org_id, n):
    for _ in range(n):
        assert api.post("/api/member", json={**MEMBER_REQ, "organization_id": org_id, "last_name": "О",
                                             "first_name": uniq("Н")}).status_code == 201


def _by_key(anon):
    r = anon.get(URL)
    assert r.status_code == 200 and r.headers["Cache-Control"] == "public, max-age=300"
    d = r.get_json()
    return d, {x["key"]: x for x in d["items"]}


def test_shape_totals_and_percent_sum(api, anon):
    d, items = _by_key(anon)
    assert set(d) == {"total_members", "items"}
    assert d["total_members"] == sum(x["members"] for x in d["items"])
    assert d["total_members"] == len(api.get("/api/member").get_json())   # хэн ч орхигдохгүй
    if d["items"]:
        assert sum(x["percent"] for x in d["items"]) == 100
    assert [x["members"] for x in d["items"]] == sorted((x["members"] for x in d["items"]), reverse=True)
    for x in d["items"]:
        assert set(x) == {"key", "school_category_id", "short_name", "name", "members", "percent"}
        assert x["members"] > 0


def test_categories_rural_and_other(api, anon, make_user):
    _, before = _by_key(anon)
    base = lambda k: before.get(k, {}).get("members", 0)   # noqa: E731
    ebs, sci, rural_school, bare = _org(api, 12), _org(api, 15), _org(api, 12), _org(api)
    _members(api, ebs["id"], 3), _members(api, sci["id"], 2)
    _members(api, rural_school["id"], 4), _members(api, bare["id"], 1)
    _, spec = make_user([])
    assert api.put(f"/api/user/{spec['id']}/scope",
                   json={"school_type": "rural", "organization_ids": [rural_school["id"]]}).status_code == 200
    _, items = _by_key(anon)
    assert items["12"]["members"] == base("12") + 3            # ХОН сургууль ЕБС-ээс хасагдсан
    assert items["12"]["short_name"] == "ЕБС" and items["12"]["name"] == "Ерөнхий боловсрол"
    assert items["15"]["members"] == base("15") + 2
    assert items["rural"]["members"] == base("rural") + 4
    assert items["rural"]["name"] == "Хөдөө, орон нутаг" and items["rural"]["school_category_id"] is None
    assert items["other"]["members"] == base("other") + 1 and items["other"]["name"] == "Бусад"
    for o in (ebs, sci, rural_school, bare):
        api.delete(f"/api/organization/{o['id']}")
    api.delete(f"/api/user/{spec['id']}")


def test_percents_largest_remainder():
    assert percents([44, 37, 11, 4, 4]) == [44, 37, 11, 4, 4]
    assert sum(percents([1, 1, 1])) == 100 and sorted(percents([1, 1, 1])) == [33, 33, 34]
    assert percents([2, 1]) == [67, 33]
    assert percents([]) == [] and percents([0, 0]) == [0, 0]
