# edu-union-backend — production контейнер (EC2 дээр docker compose-оор ажиллана).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Хамаарлууд эхэлж — код өөрчлөгдөхөд давхарга дахин ашиглагдана
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Production-д файлууд S3-т (S3_BUCKET, /opt/edu-union/.env) — доорх хавтсууд нь зөвхөн
# S3_BUCKET тохируулаагүй үеийн нөөц горим ба хуучин файлыг S3 руу зөөх скриптэд хэрэгтэй.
ENV UPLOAD_DIR=/data/uploads/member \
    CONTENT_UPLOAD_DIR=/data/uploads/content \
    FORM_UPLOAD_DIR=/data/uploads/form \
    PORT=8000

EXPOSE 8000

# --preload: аппыг мастер процесс дээр НЭГ УДАА ачаалж, дараа нь салаална.
# ensure_seeded() ажилтан бүр дээр давхар ажиллахаас (seed давхардахаас) сэргийлнэ.
# Лог: файл бичихгүй — stdout/stderr -> Docker awslogs -> CloudWatch. gunicorn-ы access
# log-ийг унтраав: core/audit.py хэрэглэгчийн мэдээлэлтэй JSON мөрийг оронд нь бичдэг.
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--timeout", "60", "--preload", \
     "--error-logfile", "-"]
