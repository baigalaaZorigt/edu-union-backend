"""admin/union/ — лавлахууд ба гишүүний дэд нөөцүүдийн тест — хуваалцсан туслахууд (test_union_refs_*.py ашиглана)."""

import pytest

from conftest import uniq


CODED_REFS = ["position", "profession", "reward_type", "structure"]
MISSING = 999999


# ----------------------------- туслахууд -----------------------------
@pytest.fixture
def member(api):
    """Шинэ байгууллага + гишүүн үүсгээд гишүүний json-г буцаана."""
    r = api.post("/api/organization", json={"name": uniq("Байгууллага ")})
    assert r.status_code == 201, r.get_json()
    org = r.get_json()
    r = api.post("/api/member", json={"organization_id": org["id"],
                                      "first_name": "Бат", "last_name": "Дорж"})
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def _new_ref(api, table, **extra):
    body = {"code": uniq("c"), "name": uniq("Нэр ")}
    body.update(extra)
    r = api.post(f"/api/{table}", json=body)
    assert r.status_code == 201, r.get_json()
    return r.get_json()
