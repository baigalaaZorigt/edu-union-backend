"""Гишүүний заавал талбарууд — овог, нэр, хүйс, төрсөн огноо, статус (member-required-fields-spec)."""
import pytest

from conftest import MEMBER_REQ

from _union_helpers import make_member, make_org


@pytest.fixture
def org(api):
    o = make_org(api)
    yield o
    api.delete(f"/api/organization/{o['id']}")


@pytest.mark.parametrize("field", ["last_name", "first_name", "gender", "birth_date", "status"])
@pytest.mark.parametrize("value", ["<missing>", None, "", "   "])
def test_create_requires_field(api, org, field, value):
    body = {**MEMBER_REQ, "organization_id": org["id"]}
    if value == "<missing>":
        del body[field]
    else:
        body[field] = value
    r = api.post("/api/member", json=body)
    assert r.status_code == 400 and field in r.get_json()["error"]


@pytest.mark.parametrize("value", ["1990-13-01", "17.05.1990", "1990", 19900517])
def test_birth_date_must_be_a_date(api, org, value):
    r = api.post("/api/member", json={**MEMBER_REQ, "organization_id": org["id"],
                                      "birth_date": value})
    assert r.status_code == 400 and "birth_date" in r.get_json()["error"]


def test_create_trims_and_keeps_rest_optional(api, org):
    r = api.post("/api/member", json={"organization_id": org["id"], "last_name": " Бат ",
                                      "first_name": " Дорж ", "gender": "эм",
                                      "birth_date": "1990-5-7", "status": " идэвхтэй "})
    assert r.status_code == 201, r.get_json()
    m = r.get_json()
    assert (m["last_name"], m["first_name"], m["status"]) == ("Бат", "Дорж", "идэвхтэй")
    assert m["birth_date"] == "1990-05-07" and m["register_number"] is None
    api.delete(f"/api/member/{m['id']}")


def test_update_is_partial_but_cannot_blank(api, org):
    m = make_member(api, org["id"])
    url = f"/api/member/{m['id']}"
    assert api.patch(url, json={"email": "a@b.mn"}).status_code == 200       # бусад нь чөлөөтэй
    for field in ("last_name", "first_name", "gender", "birth_date", "status"):
        for value in (None, "", "  "):
            r = api.put(url, json={field: value})
            assert r.status_code == 400 and field in r.get_json()["error"], (field, value)
    assert api.patch(url, json={"birth_date": "x"}).status_code == 400
    assert api.patch(url, json={"gender": "эм", "birth_date": "1985-12-31"}).status_code == 200
    got = api.get(url).get_json()
    assert got["gender"] == "эм" and got["birth_date"] == "1985-12-31"
    assert got["last_name"] == m["last_name"]
    api.delete(url)


def test_education_stays_optional(api, org):
    m = make_member(api, org["id"])
    r = api.post("/api/member_education", json={"member_id": m["id"]})
    assert r.status_code == 201, r.get_json()
    api.delete(f"/api/member/{m['id']}")
