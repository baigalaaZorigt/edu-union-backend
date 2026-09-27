"""GET /api/me/specialist — менежерийн сургуулийг хариуцсан Зөвлөх мэргэжилтэн."""
import itertools

import pytest

from conftest import uniq

_spaces = itertools.count(60)          # role.name UNIQUE — нэрийг зайгаар ялгана (strip хийгддэг)


def _specialist_role():
    return " " * next(_spaces) + "Зөвлөх мэргэжилтэн"


@pytest.fixture
def district(api):
    """Энэ тестэд л хэрэглэгдэх дүүрэг (бусад тестийн мэргэжилтэнтэй давхцахгүй)."""
    units = api.get("/api/au2").get_json()
    return units[-(next(_spaces) % 200) - 1]


def _org(api, au2, category=12):
    r = api.post("/api/organization", json={
        "name": uniq("Хариуцагч сургууль"), "org_code": f"{int(uniq('')) % 900 + 100:03d}",
        "school_category_id": category, "au1_code": au2["au1_code"], "au2_code": au2["au2_code"]})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _set_scope(api, uid, scope):
    r = api.put(f"/api/user/{uid}/scope", json=scope)
    assert r.status_code == 200, r.get_json()


def _manager(api, make_user, org_id):
    client, user = make_user([])
    _set_scope(api, user["id"], {"organization_id": org_id})
    return client


def _specialist(api, make_user, scope, **user_extra):
    _, user = make_user([], role_name=_specialist_role())
    if user_extra:
        api.patch(f"/api/user/{user['id']}", json=user_extra)
    _set_scope(api, user["id"], scope)
    return user


def test_district_match(api, make_user, district):
    org = _org(api, district)
    spec = _specialist(api, make_user, {"school_type": "general",
                                        "district_au2_code": district["au2_code"]},
                       email="spec@example.mn")
    r = _manager(api, make_user, org["id"]).get("/api/me/specialist")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["id"] == spec["id"] and d["matched_by"] == "district" and d["organization_id"] == org["id"]
    assert d["email"] == "spec@example.mn" and d["last_name"] == "Тест"
    assert "password_hash" not in d and "username" not in d


def test_rural_assignment_wins(api, make_user, district):
    org = _org(api, district)
    _specialist(api, make_user, {"school_type": "general", "district_au2_code": district["au2_code"]})
    rural = _specialist(api, make_user, {"school_type": "rural", "organization_ids": [org["id"]]})
    d = _manager(api, make_user, org["id"]).get("/api/me/specialist").get_json()
    assert d["id"] == rural["id"] and d["matched_by"] == "rural"


def test_no_match_cases(api, make_user, district):
    org = _org(api, district)
    mgr = _manager(api, make_user, org["id"])
    r = mgr.get("/api/me/specialist")
    assert r.status_code == 404 and r.get_json()["error"] == "Таны сургуулийг хариуцсан мэргэжилтэн олдсонгүй"
    _specialist(api, make_user, {"school_type": "preschool",                 # өөр ангилал
                                 "district_au2_code": district["au2_code"]})
    other = _org(api, district)
    _specialist(api, make_user, {"school_type": "rural", "organization_ids": [other["id"]]})
    _, not_spec = make_user([])                                              # мэргэжилтэн биш дүр
    _set_scope(api, not_spec["id"], {"school_type": "general",
                                     "district_au2_code": district["au2_code"]})
    inactive = _specialist(api, make_user, {"school_type": "general",
                                            "district_au2_code": district["au2_code"]})
    api.patch(f"/api/user/{inactive['id']}", json={"is_active": 0})
    assert mgr.get("/api/me/specialist").status_code == 404


def test_only_managers(api, anon, make_user, district):
    assert anon.get("/api/me/specialist").status_code == 401
    r = api.get("/api/me/specialist")                                        # admin — хүрээгүй
    assert r.status_code == 403 and "error" in r.get_json()
    spec_client, spec = make_user([], role_name=_specialist_role())
    _set_scope(api, spec["id"], {"school_type": "general", "district_au2_code": district["au2_code"]})
    assert spec_client.get("/api/me/specialist").status_code == 403
