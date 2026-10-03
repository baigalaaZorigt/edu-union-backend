"""created_by / updated_by — session өөрөө бөглөж (core/orm/stamp.py), GET бүр буцаана."""
import pytest

from conftest import uniq

LISTS = ["/api/member", "/api/organization", "/api/user", "/api/role", "/api/admin/news",
         "/api/menu", "/api/banner", "/api/partner", "/api/school_category", "/api/position",
         "/api/profession", "/api/education_degree", "/api/reward_type", "/api/structure",
         "/api/salary_scale", "/api/au1", "/api/au2", "/api/horoo", "/api/contact",
         "/api/admin/suggestions", "/api/admin/complaints", "/api/member_education",
         "/api/member_reward", "/api/member_file"]


def _first(body):
    if isinstance(body, dict):
        body = body.get("items", body.get("data"))
    return body[0] if body else None


@pytest.mark.parametrize("url", LISTS)
def test_lists_carry_audit_fields(api, url):
    row = _first(api.get(url).get_json())
    if row is None:
        pytest.skip("хоосон жагсаалт")
    assert "created_by" in row and "updated_by" in row, row.keys()


def test_portal_settings_carries_updated_by(api):
    assert "updated_by" in api.get("/api/portal_settings").get_json()


def test_create_and_update_are_stamped(api, make_user):
    u, user = make_user(["position.create", "position.update", "position.read"])
    assert user["created_by"] == 1 and user["updated_by"] is None
    pid = u.post("/api/position", json={"code": uniq("c"), "name": uniq("n")}).get_json()["id"]
    row = u.get(f"/api/position/{pid}").get_json()
    assert row["created_by"] == user["id"] and row["updated_by"] is None
    assert api.put(f"/api/position/{pid}", json={"name": uniq("n")}).status_code == 200
    row = api.get(f"/api/position/{pid}").get_json()
    assert row["created_by"] == user["id"] and row["updated_by"] == 1


def test_guest_feedback_has_no_creator(api, anon):
    r = anon.post("/api/portal/suggestions", json={
        "name": "Зочин", "email": "a@b.mn", "phone": "99112233", "message": uniq("m")})
    assert r.status_code == 201
    row = next(i for i in api.get("/api/admin/suggestions?per_page=100").get_json()["items"]
               if i["id"] == r.get_json()["id"])
    assert row["created_by"] is None
