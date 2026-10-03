"""core/auth.py: гишүүн харах/бүртгэх/засах эрх нь маягтын лавлагааг УНШИХ эрхийг дагуулна."""
import pytest

LOOKUPS = ["/api/position", "/api/profession", "/api/salary_scale", "/api/education_degree",
           "/api/reward_type", "/api/au1", "/api/au2", "/api/au3?au2_code=01101"]


@pytest.mark.parametrize("perm", ["member.read", "member.create", "member.update"])
def test_member_writer_reads_lookups_without_their_permission(make_user, perm):
    u, _ = make_user([perm])
    for url in LOOKUPS:
        assert u.get(url).status_code == 200, url
    assert u.get("/api/position/1").status_code == 200


def test_other_permissions_still_403_on_lookups(make_user):
    u, _ = make_user(["member.delete", "organization.read", "member_education.create"])
    for url in LOOKUPS:
        assert u.get(url).status_code == 403, url


def test_member_writer_cannot_change_lookups_or_read_others(make_user):
    u, _ = make_user(["member.create", "member.update"])
    assert u.post("/api/position", json={"code": "zz", "name": "x"}).status_code == 403
    assert u.put("/api/position/1", json={"name": "x"}).status_code == 403
    assert u.delete("/api/position/1").status_code == 403
    for url in ("/api/structure", "/api/school_category", "/api/user", "/api/role"):
        assert u.get(url).status_code == 403, url
