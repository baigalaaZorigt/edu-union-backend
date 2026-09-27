"""Жагсаалтын хуудаслалт (сонголтоор) — core/helpers.fetch_page / slice_page / list_json.

?page= эсвэл ?per_page= өгвөл {items, total, page, per_page, pages}; өгөөгүй бол хуучин массив.
"""
import pytest

LISTS = [
    "/api/au1", "/api/au2", "/api/au3", "/api/au2?au1_code=011", "/api/school_category",
    "/api/horoo", "/api/organization", "/api/member", "/api/contact", "/api/salary_request",
    "/api/salary_scale", "/api/education_degree", "/api/position", "/api/profession",
    "/api/reward_type", "/api/structure", "/api/member_education", "/api/member_reward",
    "/api/member_file", "/api/permission", "/api/permission?resource=user", "/api/role",
    "/api/user", "/api/menu", "/api/page", "/api/page_block", "/api/page_image",
    "/api/page_file", "/api/page_video", "/api/banner", "/api/partner",
]


def _with(url, qs):
    return url + ("&" if "?" in url else "?") + qs


@pytest.mark.parametrize("url", LISTS)
def test_list_paginates_consistently_with_full_array(api, url):
    full = api.get(url)
    assert full.status_code == 200
    full = full.get_json()
    assert isinstance(full, list)                          # параметргүй — хуучин массив
    r = api.get(_with(url, "per_page=2"))
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert set(d) == {"items", "total", "page", "per_page", "pages"}
    assert (d["total"], d["page"], d["per_page"]) == (len(full), 1, 2)
    assert d["pages"] == (len(full) + 1) // 2
    assert d["items"] == full[:2]                          # ижил эрэмбэ, ижил хэлбэр
    if len(full) > 2:
        assert api.get(_with(url, "page=2&per_page=2")).get_json()["items"] == full[2:4]
    last = api.get(_with(url, f"page={d['pages'] + 1}&per_page=2")).get_json()
    assert last["items"] == [] and last["total"] == len(full)


def test_large_list_defaults_and_caps(api):
    d = api.get("/api/au3?page=1").get_json()                  # per_page анхдагч 20
    assert d["per_page"] == 20 and len(d["items"]) == 20 and d["total"] > 1000
    assert api.get("/api/au3?per_page=500").get_json()["per_page"] == 100
    assert api.get("/api/au3?per_page=0").get_json()["per_page"] == 1
    assert api.get("/api/au3?page=-3&per_page=5").get_json()["page"] == 1


@pytest.mark.parametrize("qs", ["page=x", "per_page=abc", "page=1.5"])
def test_non_numeric_is_400(api, qs):
    r = api.get("/api/member?" + qs)
    assert r.status_code == 400 and "error" in r.get_json()


def test_filters_apply_before_paging(api):
    by_res = api.get("/api/permission?resource=user").get_json()
    d = api.get("/api/permission?resource=user&per_page=3").get_json()
    assert d["total"] == len(by_res) == 4
    assert all(p["resource"] == "user" for p in d["items"])


def test_menu_tree_is_never_paged(api):
    tree = api.get("/api/menu?tree=1&per_page=1").get_json()
    assert isinstance(tree, list) and len(tree) > 1


def test_role_list_page_carries_permissions(api):
    d = api.get("/api/role?per_page=1").get_json()
    assert "permissions" in d["items"][0]


def test_my_organizations_keeps_items_shape(api):
    plain = api.get("/api/me/organizations").get_json()
    assert set(plain) == {"items"}
    d = api.get("/api/me/organizations?per_page=1").get_json()
    assert set(d) == {"items", "total", "page", "per_page", "pages"}
    assert d["total"] == len(plain["items"])


def test_portal_forms_paged_after_active_filter(api, anon):
    full = anon.get("/api/portal/forms?active=1").get_json()
    d = anon.get("/api/portal/forms?active=1&per_page=1").get_json()
    assert d["total"] == len(full) and d["items"] == full[:1]
