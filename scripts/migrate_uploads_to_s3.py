"""Сервер дээрх хуучин байршуулсан файлуудыг S3 руу нэг удаа зөөнө (идемпотент).

    S3_BUCKET=... python scripts/migrate_uploads_to_s3.py            # хуулна
    S3_BUCKET=... python scripts/migrate_uploads_to_s3.py --dry-run  # юу хуулагдахыг л харуулна

Контейнер дотор ажиллуулна (/data volume-д хуучин файлууд бий):

    docker compose run --rm --no-deps -T app python scripts/migrate_uploads_to_s3.py

UPLOAD_DIR / CONTENT_UPLOAD_DIR / FORM_UPLOAD_DIR хавтас бүрийн файлыг core/storage.py-ийн
түлхүүрээр (`uploads/<area>/<харьцангуй нэр>`) хуулна — DB-гийн URL өөрчлөгдөхгүй. S3-т
аль хэдийн байгаа (ижил хэмжээтэй) файлыг алгасна. Локал файлыг УСТГАХГҮЙ — шалгаад
гараар арилгана.
"""
import mimetypes
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.storage as storage  # noqa: E402
from admin.content.storage import STORE as CONTENT  # noqa: E402
from admin.union.common import MEMBER_STORE as MEMBER  # noqa: E402
from core.forms_core import STORE as FORM  # noqa: E402


def _remote_sizes(client, prefix):
    pages = client.get_paginator("list_objects_v2").paginate(
        Bucket=storage.S3_BUCKET, Prefix=prefix)
    return {o["Key"]: o["Size"] for p in pages for o in p.get("Contents", [])}


def main(dry_run=False):
    if not storage.S3_BUCKET:
        sys.exit("S3_BUCKET тохируулаагүй байна")
    client = storage.s3()
    total = copied = skipped = 0
    for area in (CONTENT, FORM, MEMBER):
        remote = _remote_sizes(client, area._key(""))
        if not os.path.isdir(area.local_dir):
            print(f"{area.area}: {area.local_dir} алга — алгаслаа")
            continue
        for root, _, files in os.walk(area.local_dir):
            for fname in files:
                path = os.path.join(root, fname)
                name = os.path.relpath(path, area.local_dir).replace(os.sep, "/")
                key = area._key(name)
                total += 1
                if remote.get(key) == os.path.getsize(path):
                    skipped += 1
                    continue
                print(("[dry-run] " if dry_run else "") + f"{path} -> s3://{storage.S3_BUCKET}/{key}")
                if not dry_run:
                    ctype = mimetypes.guess_type(fname)[0] or "application/octet-stream"
                    client.upload_file(path, storage.S3_BUCKET, key,
                                       ExtraArgs={"ContentType": ctype})
                copied += 1
    print(f"Нийт {total}, хуулсан {copied}, аль хэдийн байсан {skipped}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
