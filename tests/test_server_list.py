"""Жагсаалтын server-side хайлт / шүүлт / эрэмбэ — server_list_api_spec.md (core/list_query.py).

GET /api/user, /api/member, /api/organization.
"""
import pytest

from conftest import MEMBER_REQ, uniq


def _org(api, **kw):
    body = {"name": uniq("Жагсаалт сургууль"), "org_code": f"{int(uniq('')) % 900 + 100:03d}",
            "school_category_id": 12, **kw}
    r = api.post("/api/organization", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _member(api, org_id, **kw):
    body = {**MEMBER_REQ, "organization_id": org_id, "last_name": "Бат",
            "first_name": uniq("Дорж"), **kw}
    r = api.post("/api/member", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _ids(r):
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    return [x["id"] for x in (d["items"] if isinstance(d, dict) else d)]


@pytest.fixture
def three(api):
    """Нэг байгууллага + 3 гишүүн (нэр, хүйс, төрсөн он, утас ялгаатай)."""
    org = _org(api)
    a = _member(api, org["id"], last_name="Аюуш", first_name="Сараа", gender="эм",
                birth_date="1985-02-03", register_number="УБ85020311")
    b = _member(api, org["id"], last_name="Болд", first_name="Тэмүүлэн", gender="эр",
                birth_date="1990-06-07")
    c = _member(api, org["id"], last_name="ЦЭРЭН", first_name="Ганаа", gender="эр",
                birth_date="1990-11-12")
    api.post("/api/contact", json={"owner_type": "member", "owner_id": b["id"], "type": "утас",
                                   "value": "99118877"})
    return org, a, b, c


def test_member_search_is_case_insensitive_cyrillic(api, three):
    org, a, b, c = three
    base = f"/api/member?organization_id={org['id']}"
    assert _ids(api.get(base + "&search=цэрэн")) == [c["id"]]          # ЦЭРЭН
    assert _ids(api.get(base + "&search=САРАА")) == [a["id"]]
    assert _ids(api.get(base + "&search=9911887")) == [b["id"]]        # утас (contact)
    assert _ids(api.get(base + "&search=уб8502")) == [a["id"]]         # регистр
    assert _ids(api.get(base + "&search=%25")) == []                   # % нь wildcard биш


def test_member_column_filters_and(api, three):
    org, a, b, c = three
    base = f"/api/member?organization_id={org['id']}"
    assert sorted(_ids(api.get(base + "&gender=эр"))) == sorted([b["id"], c["id"]])
    assert sorted(_ids(api.get(base + "&birth_year=1990"))) == sorted([b["id"], c["id"]])
    assert _ids(api.get(base + "&birth_year=1990&name=ганаа")) == [c["id"]]
    assert _ids(api.get(base + "&phone_fax=118877")) == [b["id"]]
    assert _ids(api.get(base + "&organization=" + org["name"][:6].lower()))  # join нэр
    assert len(_ids(api.get(base + "&name="))) == 3                   # хоосон -> шүүлтгүй
    st = api.get("/api/member_status").get_json()[0]
    api.patch(f"/api/member/{a['id']}", json={"status_id": st["id"]})
    assert a["id"] in _ids(api.get(base + f"&member_status_id={st['id']}"))
    assert api.get(base + "&birth_year=abc").status_code == 422


def test_member_sort_and_paging(api, three):
    org, a, b, c = three
    base = f"/api/member?organization_id={org['id']}"
    assert _ids(api.get(base + "&sort=name&order=asc")) == [a["id"], b["id"], c["id"]]
    assert _ids(api.get(base + "&sort=birth_year&order=desc")) == [c["id"], b["id"], a["id"]]
    # анхдагч: created_at desc, id desc (тэнцүү created_at-д id-аар тогтвортой)
    assert _ids(api.get(base)) == [c["id"], b["id"], a["id"]]
    d = api.get(base + "&sort=name&order=asc&page=2&per_page=2").get_json()
    assert (d["total"], d["pages"], d["page"], [x["id"] for x in d["items"]]) == (3, 2, 2, [c["id"]])
    assert api.get(base + "&page=9&per_page=2").get_json()["items"] == []
    d = api.get(base + "&search=байхгүй-нэр&page=1").get_json()
    assert (d["total"], d["pages"], d["per_page"]) == (0, 1, 10)


@pytest.mark.parametrize("qs", ["sort=password_hash", "sort=id;drop", "order=up",
                                "page=x", "per_page=1.5"])
@pytest.mark.parametrize("url", ["/api/member", "/api/organization", "/api/user"])
def test_bad_params_are_422(api, url, qs):
    r = api.get(f"{url}?{qs}")
    assert r.status_code == 422
    body = r.get_json()
    assert body["message"] == body["error"]


def test_organization_search_sort_filters(api):
    o1 = _org(api, name=uniq("Альфа сургууль"), contact_name="Дулмаа")
    o2 = _org(api, name=uniq("Бета сургууль"), registration_number="7766554")
    _member(api, o2["id"])
    _member(api, o2["id"])
    assert _ids(api.get(f"/api/organization?search={o1['full_code']}")) == [o1["id"]]
    dashed = f"{o1['full_code'][:2]}-{o1['full_code'][2:]}"
    assert _ids(api.get(f"/api/organization?org_code={dashed}")) == [o1["id"]]
    assert o1["id"] in _ids(api.get("/api/organization?leader=ДУЛМ"))
    assert _ids(api.get("/api/organization?registration_number=776655")) == [o2["id"]]
    short = next(c["short_name"] for c in api.get("/api/school_category").get_json()
                 if c["id"] == 12)
    typed = _ids(api.get(f"/api/organization?school_type={short.upper()}&per_page=100"))
    assert o1["id"] in typed and o2["id"] in typed
    d = api.get("/api/organization?sort=total_members&order=desc&per_page=100").get_json()
    counts = [x["total_members"] for x in d["items"]]
    assert counts == sorted(counts, reverse=True)
    assert d["total"] == len(api.get("/api/organization").get_json())


def test_user_search_filters_sort(api):
    role = api.post("/api/role", json={"name": uniq("Жагсаалтын дүр")}).get_json()
    names = [("Энх", "Билгүүн"), ("Анар", "Золзаяа")]
    users = []
    for last, first in names:
        r = api.post("/api/user", json={"username": uniq("9911"), "password": "Pass1234",
                                        "last_name": last, "first_name": first,
                                        "role_id": role["id"], "email": f"{uniq('m')}@x.mn"})
        assert r.status_code == 201, r.get_json()
        users.append(r.get_json())
    base = f"/api/user?role_id={role['id']}"
    assert _ids(api.get(base + "&search=БИЛГҮҮН")) == [users[0]["id"]]
    assert _ids(api.get(base + "&search=" + users[1]["username"])) == [users[1]["id"]]
    assert len(_ids(api.get(base + "&role_name=" + role["name"].lower()))) == 2
    assert _ids(api.get(base + "&sort=name&order=asc")) == [users[1]["id"], users[0]["id"]]
    api.patch(f"/api/user/{users[0]['id']}", json={"is_active": 0})
    assert _ids(api.get(base + "&is_active=0")) == [users[0]["id"]]
    d = api.get(base + "&per_page=1").get_json()
    assert d["total"] == 2 and d["pages"] == 2 and "scope" in d["items"][0]
