"""Хүрээтэй хэрэглэгч байгууллагыг хүрээнээсээ гадуур (хаяг / ангилал) бүртгэж, зөөж болохгүй."""

from conftest import uniq

from _union_helpers import AU1, AU2, make_org

PERMS = [f"organization.{a}" for a in ("read", "create", "update", "delete")]
OTHER_AU2 = "01104"


def _scoped(api, make_user, scope):
    u, user = make_user(PERMS)
    r = api.put(f"/api/user/{user['id']}/scope", json=scope)
    assert r.status_code == 200, r.get_json()
    return u, user


def _body(**kw):
    return {"name": uniq("Сургууль "), "school_category_id": 12, "au1_code": AU1,
            "au2_code": AU2, **kw}


def test_district_scope_create_and_move(api, make_user):
    """Хуучин "бүхэл дүүрэг" хүрээ: зөвхөн оноосон дүүрэг + ангилалд бүртгэнэ."""
    u, _ = _scoped(api, make_user, {"school_type": "general", "district_au2_code": AU2})
    r = u.post("/api/organization", json=_body(au2_code=OTHER_AU2))
    assert r.status_code == 403 and AU2 in r.get_json()["error"]
    assert u.post("/api/organization", json=_body(au2_code=None)).status_code == 403   # хаяггүй
    assert u.post("/api/organization", json=_body(au1_code="021")).status_code == 403  # өөр аймаг
    assert u.post("/api/organization", json=_body(school_category_id=11)).status_code == 403

    r = u.post("/api/organization", json=_body())
    assert r.status_code == 201, r.get_json()
    oid = r.get_json()["id"]
    assert u.get(f"/api/organization/{oid}").status_code == 200       # өөрийнхөө бүртгэснийг харна
    assert oid in {o["id"] for o in u.get("/api/organization").get_json()}

    # засахад: хаяг/ангиллыг хүрээнээс гаргахгүй, бусад талбар чөлөөтэй
    assert u.put(f"/api/organization/{oid}", json={"au2_code": OTHER_AU2}).status_code == 403
    assert u.patch(f"/api/organization/{oid}", json={"au2_code": ""}).status_code == 403
    assert u.patch(f"/api/organization/{oid}", json={"school_category_id": 11}).status_code == 403
    assert u.patch(f"/api/organization/{oid}", json={"name": "Шинэ нэр"}).status_code == 200
    assert u.put(f"/api/organization/{oid}", json={"au2_code": AU2, "address": "1-р хороо"}
                 ).status_code == 200
    assert api.get(f"/api/organization/{oid}").get_json()["au2_code"] == AU2
    assert u.delete(f"/api/organization/{oid}").status_code == 200


def test_picked_scope_adopts_new_org(api, make_user):
    """Сонгосон сургуулиудын хүрээ: шинэ байгууллага organization_ids-д автоматаар нэмэгдэнэ."""
    first = make_org(api, cat=12, au1_code=AU1, au2_code=AU2)
    u, user = _scoped(api, make_user, {"school_type": "general", "district_au2_code": AU2,
                                       "organization_ids": [first["id"]]})
    assert u.post("/api/organization", json=_body(au2_code=OTHER_AU2)).status_code == 403
    r = u.post("/api/organization", json=_body())
    assert r.status_code == 201, r.get_json()
    oid = r.get_json()["id"]
    assert api.get(f"/api/user/{user['id']}/scope").get_json()["organization_ids"] \
        == [first["id"], oid]
    assert {o["id"] for o in u.get("/api/organization").get_json()} == {first["id"], oid}
    assert u.patch(f"/api/organization/{oid}", json={"name": "Засав"}).status_code == 200
    for i in (oid, first["id"]):
        api.delete(f"/api/organization/{i}")


def test_rural_scope_without_district_any_address(api, make_user):
    """ХОН (дүүрэг оноогоогүй): хаяг, ангилал чөлөөтэй; шинэ сургууль хүрээнд орно."""
    u, user = _scoped(api, make_user, {"school_type": "rural", "organization_ids": []})
    r = u.post("/api/organization", json=_body(au2_code=OTHER_AU2, school_category_id=11))
    assert r.status_code == 201, r.get_json()
    oid = r.get_json()["id"]
    assert [o["id"] for o in u.get("/api/organization").get_json()] == [oid]
    api.delete(f"/api/organization/{oid}")


def test_manager_cannot_create_and_admin_unrestricted(api, make_user):
    school = make_org(api, cat=12, au1_code=AU1, au2_code=AU2)
    u, _ = _scoped(api, make_user, {"organization_id": school["id"]})
    assert u.post("/api/organization", json=_body()).status_code == 403
    assert u.patch(f"/api/organization/{school['id']}", json={"au2_code": OTHER_AU2}
                   ).status_code == 200                      # менежерт дүүрэг оноогоогүй
    r = api.post("/api/organization", json=_body(au2_code=OTHER_AU2))   # admin — хүрээгүй
    assert r.status_code == 201
    for i in (r.get_json()["id"], school["id"]):
        api.delete(f"/api/organization/{i}")
