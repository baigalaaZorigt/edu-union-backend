"""Хамрах хүрээ — ангилалтай төрөлд ч тодорхой сургуулиудыг (organization_ids) сонгоно."""
from _union_helpers import AU1, AU2, make_org

from test_me_specialist import _manager, _specialist
from test_union_scope import ORG_MEMBER_PERMS, _check_scope, _set_scope, two_orgs  # noqa: F401


def test_picked_schools_are_the_scope(api, make_user, two_orgs):   # noqa: F811
    ins, out, m_in, m_out = two_orgs
    u, user = make_user(ORG_MEMBER_PERMS)
    # дүүрэг нь зөвхөн шүүлтүүр: out-ийн дүүргийг өгсөн ч хүрээ нь сонгосон сургууль (ins)
    r = api.put(f"/api/user/{user['id']}/scope", json={
        "school_type": "general", "district_au2_code": "01104", "organization_ids": [ins["id"]]})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["organization_ids"] == [ins["id"]]
    _check_scope(u, ins, out, m_in, m_out)
    # дүүрэггүйгээр ч болно
    _set_scope(api, user["id"], {"school_type": "general", "organization_ids": [ins["id"]]})
    _check_scope(u, ins, out, m_in, m_out)


def test_validation(api, make_user, two_orgs):                     # noqa: F811
    ins = two_orgs[0]
    _, user = make_user([])
    url = f"/api/user/{user['id']}/scope"
    other = make_org(api, cat=14, au1_code=AU1, au2_code=AU2)
    assert api.put(url, json={"school_type": "general"}).status_code == 400          # сургуульгүй
    r = api.put(url, json={"school_type": "general", "organization_ids": [ins["id"], other["id"]]})
    assert r.status_code == 400 and "ангилалд" in r.get_json()["error"]              # өөр ангилал
    assert api.put(url, json={"school_type": "higher",
                              "organization_ids": [other["id"]]}).status_code == 200
    assert api.put(url, json={"school_type": "general",
                              "organization_ids": [99999999]}).status_code == 400
    # ХОН-д ангилал шалгахгүй; хуучин "бүхэл дүүрэг" хэлбэр хэвээр хадгалагдана
    assert api.put(url, json={"school_type": "rural",
                              "organization_ids": [ins["id"], other["id"]]}).status_code == 200
    assert api.put(url, json={"school_type": "general",
                              "district_au2_code": AU2}).status_code == 200
    api.delete(f"/api/organization/{other['id']}")


def test_my_specialist_by_picked_school(api, make_user, two_orgs):  # noqa: F811
    ins, out = two_orgs[0], two_orgs[1]
    spec = _specialist(api, make_user, {"school_type": "general", "organization_ids": [ins["id"]]})
    d = _manager(api, make_user, ins["id"]).get("/api/me/specialist").get_json()
    assert d["id"] == spec["id"] and d["matched_by"] == "organization"
    # сонгоогүй сургуулийг (out) энэ мэргэжилтэн хариуцахгүй
    r = _manager(api, make_user, out["id"]).get("/api/me/specialist")
    assert r.status_code == 404 or r.get_json()["id"] != spec["id"]
    # мэргэжилтэн өөрөө менежер биш -> 403
    client, user = make_user([])
    _set_scope(api, user["id"], {"school_type": "general", "organization_ids": [ins["id"]]})
    assert client.get("/api/me/specialist").status_code == 403
