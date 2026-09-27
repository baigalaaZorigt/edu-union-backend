"""Порталын нүүр хуудасны статистик (Blueprint, токенгүй).

    GET /api/portal/membership_structure   — «Гишүүнчлэлийн бүтэц» дугуй диаграм
        {total_members, items: [{key, school_category_id, short_name, name, members, percent}]}

Бүлэг:
  * "rural" — Хөдөө, орон нутаг (ХОН): ХОН мэргэжилтэнд (user_scope.school_type='rural')
    organization_ids-ээр ОНООГДСОН сургуулиудын гишүүд. Систем ХОН-ыг ингэж тодорхойлдог
    (ангилал биш, шууд оноолт) — эдгээр гишүүд үндсэн ангиллаасаа ХАСАГДАНА (давхардахгүй).
  * сургуулийн ангилал (school_category) бүрээр; ангилалгүй сургуулийн гишүүд -> "other".
Гишүүнгүй бүлэг гарахгүй; гишүүдийн тоогоор буурахаар; percent нь бүхэл тоо, нийлбэр нь
яг 100 (largest remainder). Зөвхөн нэгтгэсэн тоо — хувь хүний мэдээлэл агуулахгүй.
Нүүр хуудсанд байнга дуудагддаг тул 5 минутын Cache-Control.
"""
import json

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from core.orm import session
from core.orm.models import Member, Organization, SchoolCategory, UserScope
from core.scope_core import RURAL

bp = Blueprint("portal_stats", __name__)

CACHE_SECONDS = 300
RURAL_ITEM = {"key": "rural", "school_category_id": None, "short_name": "ХОН",
              "name": "Хөдөө, орон нутаг"}
OTHER_ITEM = {"key": "other", "school_category_id": None, "short_name": None,
              "name": "Бусад"}                  # ангилал оноогоогүй сургуулийн гишүүд


def _rural_org_ids(s):
    ids = set()
    for raw in s.scalars(select(UserScope.organization_ids).where(UserScope.school_type == RURAL)):
        try:
            ids |= {int(i) for i in json.loads(raw or "[]") if str(i).isdigit()}
        except (TypeError, ValueError):
            continue
    return ids


def percents(counts):
    """Бүхэл хувь, нийлбэр нь яг 100 (largest remainder). Хоосон бол []."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    exact = [c * 100 / total for c in counts]
    out = [int(e) for e in exact]
    for i in sorted(range(len(counts)), key=lambda i: exact[i] - out[i], reverse=True)[:100 - sum(out)]:
        out[i] += 1
    return out


@bp.route("/api/portal/membership_structure", methods=["GET"])
def membership_structure():
    s = session()
    rural = _rural_org_ids(s)
    per_org = s.execute(select(Member.organization_id, Organization.school_category_id,
                               func.count(Member.id))
                        .join(Organization, Organization.id == Member.organization_id)
                        .group_by(Member.organization_id, Organization.school_category_id)).all()
    by_key = {}
    for org_id, cat_id, n in per_org:
        key = "rural" if org_id in rural else (str(cat_id) if cat_id is not None else "other")
        by_key[key] = by_key.get(key, 0) + n
    cats = {c.id: c for c in s.scalars(select(SchoolCategory))}
    items = []
    for key, n in by_key.items():
        if key in ("rural", "other"):
            items.append({**(RURAL_ITEM if key == "rural" else OTHER_ITEM), "members": n})
        else:
            c = cats.get(int(key))
            items.append({"key": key, "school_category_id": int(key),
                          "short_name": c.short_name if c else None,
                          "name": c.full_name if c else None, "members": n})
    items.sort(key=lambda x: (-x["members"], x["key"]))
    for item, p in zip(items, percents([x["members"] for x in items])):
        item["percent"] = p
    resp = jsonify(total_members=sum(x["members"] for x in items), items=items)
    resp.headers["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return resp
