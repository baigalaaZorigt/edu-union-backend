"""Файлын сан — S3 (production) эсвэл локал диск (хөгжүүлэлт, тест).

`S3_BUCKET` орчны хувьсагч өгөгдсөн бол БҮХ байршуулсан файл S3-т хадгалагдаж, аппын
сервер дээр нэг ч файл үлдэхгүй (контейнер stateless). Өгөөгүй бол хуучин шигээ
`UPLOAD_DIR`-уудад бичнэ — тест, локал хөгжүүлэлт өөрчлөгдөхгүй.

Бүс (area) бүр өөрийн угтвартай: S3-ийн түлхүүр нь `<S3_PREFIX><area>/<name>`
(ж: `uploads/content/ab12.png`, `uploads/member/7/cd34.pdf`). DB-д хадгалагдсан URL /
stored_name ӨӨРЧЛӨГДӨХГҮЙ — `/uploads/content/<name>` зэрэг замууд хуучнаараа
ажиллаж, файлыг S3-аас уншиж буцаана (гишүүний PDF токенгүйгээр задгай гарахгүй).

S3-ийн эрх нь EC2-ийн instance role-оос (IMDS) ирнэ — аппын кодод түлхүүр байхгүй.
"""
import io
import os

from flask import send_file, send_from_directory

S3_BUCKET = os.environ.get("S3_BUCKET", "").strip()
S3_PREFIX = os.environ.get("S3_PREFIX", "uploads/")
AWS_REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

_client = None


def s3():
    """boto3 S3 client (нэг удаа үүсгэнэ). boto3 зөвхөн S3 ашиглах үед импортлогдоно."""
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("s3", region_name=AWS_REGION)
    return _client


def _missing(err):
    return err.response.get("Error", {}).get("Code") in ("NoSuchKey", "404", "NotFound")


class Area:
    """Нэг төрлийн файлын сан (content / form / member).

    name — area дотор харьцангуй нэр ("ab12.png", "7/cd34.pdf"); хэрэглэгчийн оролтоос
    ирсэн нэрийг дуудагч тал `os.path.basename`-аар цэвэрлэсэн байх ёстой.
    """

    def __init__(self, area, local_dir):
        self.area = area
        self.local_dir = local_dir

    def _key(self, name):
        return f"{S3_PREFIX}{self.area}/{name}"

    def _path(self, name):
        return os.path.join(self.local_dir, name)

    def save(self, name, fileobj, content_type=None):
        """werkzeug FileStorage эсвэл file-like объектыг хадгална."""
        stream = getattr(fileobj, "stream", fileobj)
        stream.seek(0)
        if S3_BUCKET:
            extra = {"ContentType": content_type} if content_type else {}
            s3().upload_fileobj(stream, S3_BUCKET, self._key(name), ExtraArgs=extra)
            return
        path = self._path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as out:
            out.write(stream.read())

    def delete(self, name):
        """Файлыг арилгана; байхгүй бол чимээгүй өнгөрнө (DB-гийн мөр аль хэдийн устсан)."""
        if S3_BUCKET:
            s3().delete_object(Bucket=S3_BUCKET, Key=self._key(name))
            return
        path = self._path(name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                folder = os.path.dirname(path)      # хоосон болсон дэд хавтас (member/<id>/)
                if folder != os.path.normpath(self.local_dir) and not os.listdir(folder):
                    os.rmdir(folder)
            except OSError:
                pass

    def names(self):
        """Area доторх бүх файлын харьцангуй нэр (өнчин файл цэвэрлэхэд)."""
        if S3_BUCKET:
            prefix = self._key("")
            pages = s3().get_paginator("list_objects_v2").paginate(
                Bucket=S3_BUCKET, Prefix=prefix)
            return [o["Key"][len(prefix):] for p in pages for o in p.get("Contents", [])]
        if not os.path.isdir(self.local_dir):
            return []
        return [os.path.relpath(os.path.join(root, f), self.local_dir)
                for root, _, files in os.walk(self.local_dir) for f in files]

    def send(self, name, mimetype=None, download_name=None):
        """Файлыг HTTP хариу болгож буцаана; олдохгүй бол None (дуудагч 404 өгнө).

        download_name өгвөл attachment болж тэр нэрээр татагдана.
        """
        attach = {"as_attachment": True, "download_name": download_name} if download_name else {}
        if S3_BUCKET:
            from botocore.exceptions import ClientError
            try:
                obj = s3().get_object(Bucket=S3_BUCKET, Key=self._key(name))
            except ClientError as err:
                if _missing(err):
                    return None
                raise
            # ≤ 20 MB тул санах ойд уншихад болно; send_file нь Content-Disposition
            # (кирилл нэр ч), Range, ETag-ийг локалтай ижил хэлбэрээр гаргана.
            data = io.BytesIO(obj["Body"].read())
            return send_file(data, mimetype=mimetype or obj.get("ContentType"),
                             download_name=download_name or os.path.basename(name),
                             **({"as_attachment": True} if download_name else {}))
        path = self._path(name)
        if not os.path.isfile(path):
            return None
        if download_name:
            return send_file(path, mimetype=mimetype, **attach)
        return send_from_directory(os.path.dirname(path), os.path.basename(path),
                                   mimetype=mimetype)
