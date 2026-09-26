"""admin/union/ — horoo / organization / member / contact / member_file — хуваалцсан туслахууд (test_union_*.py ашиглана)."""

import io
import random

from conftest import uniq


CAT = 16            # тестийн байгууллагууд энэ ангилалд (ЕБС=12-оос бусад)
AU1, AU2, AU3 = "011", "01101", "0110151"


# ----------------------------- туслахууд -----------------------------
def make_org(api, cat=CAT, **extra):
    """Давхцахгүй org_code-той байгууллага үүсгэнэ (409 бол өөр код сонгоно)."""
    for _ in range(50):
        body = {"name": uniq("Байгууллага "), "school_category_id": cat,
                "org_code": f"{random.randint(0, 999):03d}"}
        body.update(extra)
        r = api.post("/api/organization", json=body)
        if r.status_code == 409 and "org_code" not in extra:
            continue
        assert r.status_code == 201, r.get_json()
        return r.get_json()
    raise AssertionError("давхцахгүй org_code олдсонгүй")


def make_member(api, org_id, **extra):
    body = {"organization_id": org_id, "last_name": "Бат", "first_name": uniq("Дорж")}
    body.update(extra)
    r = api.post("/api/member", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def upload(api, member_id, files, note=None):
    data = {"member_id": str(member_id)}
    if note is not None:
        data["note"] = note
    data["file"] = [(io.BytesIO(b), n) for n, b in files]
    return api.post("/api/member_file", json=None, data=data,
                    content_type="multipart/form-data")


def free_org_code(api, cat):
    used = {o["org_code"] for o in api.get(f"/api/organization?school_category_id={cat}").get_json()}
    return next(f"{i:03d}" for i in random.sample(range(1000), 1000) if f"{i:03d}" not in used)
