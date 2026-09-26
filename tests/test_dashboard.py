"""admin/dashboard.py — GET /api/admin/dashboard/summary."""
from conftest import uniq

URL = "/api/admin/dashboard/summary"


def _org(api, cat=None):
    body = {"name": uniq("Сургууль")}
    if cat:
        body["school_category_id"] = cat
    r = api.post("/api/organization", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def _member(api, oid, gender):
    r = api.post("/api/member", json={"organization_id": oid, "first_name": "Гишүүн",
                                      "last_name": "Т", "gender": gender})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["id"]


def test_summary_shape(api):
    r = api.get(URL)
    assert r.status_code == 200
    d = r.get_json()
    assert set(d) == {"total_members", "total_organizations", "by_category", "gender"}
    assert set(d["gender"]) == {"male", "female"}
    cats = api.get("/api/school_category").get_json()
    assert [c["school_category_id"] for c in d["by_category"]] == sorted(c["id"] for c in cats)
    for c in d["by_category"]:
        assert set(c) == {"school_category_id", "short_name", "full_name",
                          "organization_count", "member_count"}
        assert c["organization_count"] >= 0 and c["member_count"] >= 0


def test_summary_counts_move(api):
    before = api.get(URL).get_json()
    oid = _org(api, cat=13)
    _member(api, oid, "эр")
    _member(api, oid, "эм")
    _member(api, oid, "эм")
    _member(api, oid, None)
    after = api.get(URL).get_json()
    assert after["total_organizations"] == before["total_organizations"] + 1
    assert after["total_members"] == before["total_members"] + 4
    assert after["gender"]["male"] == before["gender"]["male"] + 1
    assert after["gender"]["female"] == before["gender"]["female"] + 2

    def cat13(d):
        return next(c for c in d["by_category"] if c["school_category_id"] == 13)
    assert cat13(after)["organization_count"] == cat13(before)["organization_count"] + 1
    assert cat13(after)["member_count"] == cat13(before)["member_count"] + 4


def test_summary_requires_auth_and_permission(anon, make_user):
    assert anon.get(URL).status_code == 401
    u, _ = make_user(["member.read"])
    assert u.get(URL).status_code == 403
    u, _ = make_user(["dashboard.read"])
    assert u.get(URL).status_code == 200


def test_summary_filtered_by_scope(api, client, make_user):
    o_in = _org(api, cat=12)
    o_out = _org(api, cat=12)
    _member(api, o_in, "эр")
    _member(api, o_in, "эм")
    _member(api, o_out, "эм")

    u, user = make_user(["dashboard.read"])
    r = api.put(f"/api/user/{user['id']}/scope",
                json={"school_type": "rural", "organization_ids": [o_in]})
    assert r.status_code == 200

    d = u.get(URL).get_json()
    assert d["total_organizations"] == 1
    assert d["total_members"] == 2
    assert d["gender"] == {"male": 1, "female": 1}
    for c in d["by_category"]:
        if c["school_category_id"] == 12:
            assert c["organization_count"] == 1 and c["member_count"] == 2
        else:
            assert c["organization_count"] == 0 and c["member_count"] == 0

    # хоосон ХОН хүрээ -> бүх тоо 0 (бүгд биш)
    api.put(f"/api/user/{user['id']}/scope",
            json={"school_type": "rural", "organization_ids": []})
    d = u.get(URL).get_json()
    assert d["total_organizations"] == 0 and d["total_members"] == 0
    assert d["gender"] == {"male": 0, "female": 0}


def test_summary_district_scope(api, make_user):
    district = "01110"
    o_in = _org(api, cat=11)
    api.put(f"/api/organization/{o_in}", json={"au1_code": "011", "au2_code": district})
    _member(api, o_in, "эм")
    o_other_cat = _org(api, cat=12)
    api.put(f"/api/organization/{o_other_cat}", json={"au1_code": "011", "au2_code": district})

    u, user = make_user(["dashboard.read"])
    api.put(f"/api/user/{user['id']}/scope",
            json={"school_type": "preschool", "district_au2_code": district})
    d = u.get(URL).get_json()
    cat11 = next(c for c in d["by_category"] if c["school_category_id"] == 11)
    assert cat11["organization_count"] >= 1 and cat11["member_count"] >= 1
    assert d["total_organizations"] == cat11["organization_count"]
    for c in d["by_category"]:
        if c["school_category_id"] != 11:
            assert c["organization_count"] == 0
