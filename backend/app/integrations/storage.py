"""File storage: AWS S3 (ap-south-1, boto3) when AWS_S3_BUCKET_NAME is set, otherwise the local `uploads/` folder -
the same arrangement as the MCG platform backend. Object keys / relative paths keep the module's scheme:

    bvms/<YYYY>/<MM>/<uuid>_<original name>      evidence, replies, scanned orders
    bvms/notices/<YYYY>/<MM>/<notice no>.pdf     generated notices (+ "-signed")
    bvms/land-layers/, bvms/inspection-batches/, bvms/legacy/<YYYY>/<MM>/   uploaded source files
"""
from __future__ import annotations

import mimetypes
import os
import re
import secrets
import uuid
from pathlib import Path

from fastapi.responses import FileResponse, Response

from app.core.config import settings
from app.core.timeutil import localtime


def _clean(name: str) -> str:
    name = os.path.basename(name or "file")
    name = re.sub(r"[^\w.\-()+ ]", "_", name).strip() or "file"
    return name


def media_upload_path(filename: str) -> str:
    return f"bvms/{localtime():%Y/%m}/{uuid.uuid4().hex}_{_clean(filename)[-80:]}"


def notice_pdf_path(filename: str) -> str:
    return f"bvms/notices/{localtime():%Y/%m}/{_clean(filename)}"


def dated_path(prefix: str, filename: str) -> str:
    return f"{prefix.strip('/')}/{localtime():%Y/%m}/{_clean(filename)}"


def _suffixed(relpath: str) -> str:
    stem, ext = os.path.splitext(relpath)
    return f"{stem}_{secrets.token_urlsafe(5)}{ext}"


# ---------------------------------------------------------------- local
class LocalStorage:
    name = "local"

    def root(self) -> Path:
        root = Path(settings.UPLOADS_DIR)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def abspath(self, relpath: str) -> Path:
        return self.root() / relpath

    def exists(self, relpath: str | None) -> bool:
        return bool(relpath) and self.abspath(relpath).is_file()

    def save_bytes(self, relpath: str, data: bytes) -> str:
        while self.exists(relpath):
            relpath = _suffixed(relpath)
        p = self.abspath(relpath)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return relpath

    def read_bytes(self, relpath: str) -> bytes:
        return self.abspath(relpath).read_bytes()

    def delete(self, relpath: str | None) -> None:
        if relpath:
            try:
                self.abspath(relpath).unlink()
            except FileNotFoundError:
                pass

    def url(self, relpath: str | None) -> str | None:
        return (settings.UPLOADS_URL.rstrip("/") + "/" + relpath.lstrip("/")) if relpath else None

    def absolute_url(self, request, relpath: str | None) -> str | None:
        u = self.url(relpath)
        if not u or request is None:
            return u
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
        return f"{proto}://{host}{u}"

    def file_response(self, relpath: str, media_type: str, filename: str, inline: bool = True) -> Response:
        disp = "inline" if inline else "attachment"
        return FileResponse(str(self.abspath(relpath)), media_type=media_type, headers={"Content-Disposition": f'{disp}; filename="{filename}"'})


# ---------------------------------------------------------------- S3
class S3Storage:
    name = "s3"

    def __init__(self):
        import boto3
        kw = {"region_name": settings.AWS_REGION}
        if settings.AWS_ACCESS_KEY_ID:
            kw.update(aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)
        self.client = boto3.client("s3", **kw)
        self.bucket = settings.AWS_S3_BUCKET_NAME

    def abspath(self, relpath: str):
        return None

    def exists(self, relpath: str | None) -> bool:
        if not relpath:
            return False
        try:
            self.client.head_object(Bucket=self.bucket, Key=relpath)
            return True
        except Exception:
            return False

    def save_bytes(self, relpath: str, data: bytes) -> str:
        while self.exists(relpath):
            relpath = _suffixed(relpath)
        ctype = mimetypes.guess_type(relpath)[0] or "application/octet-stream"
        self.client.put_object(Bucket=self.bucket, Key=relpath, Body=data, ContentType=ctype)
        return relpath

    def read_bytes(self, relpath: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=relpath)["Body"].read()

    def delete(self, relpath: str | None) -> None:
        if relpath:
            try:
                self.client.delete_object(Bucket=self.bucket, Key=relpath)
            except Exception:
                pass

    def url(self, relpath: str | None) -> str | None:
        if not relpath:
            return None
        base = settings.AWS_S3_PUBLIC_BASE.rstrip("/") or f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com"
        return f"{base}/{relpath.lstrip('/')}"

    def absolute_url(self, request, relpath: str | None) -> str | None:
        return self.url(relpath)

    def file_response(self, relpath: str, media_type: str, filename: str, inline: bool = True) -> Response:
        disp = "inline" if inline else "attachment"
        return Response(content=self.read_bytes(relpath), media_type=media_type, headers={"Content-Disposition": f'{disp}; filename="{filename}"'})


_backend = None


def backend():
    global _backend
    want = "s3" if settings.s3_enabled else "local"
    if _backend is None or _backend.name != want:
        _backend = S3Storage() if want == "s3" else LocalStorage()
    return _backend


def ensure_local() -> Path:
    return LocalStorage().root()


def save_bytes(relpath: str, data: bytes) -> str:
    return backend().save_bytes(relpath, data)


def read_bytes(relpath: str) -> bytes:
    return backend().read_bytes(relpath)


def exists(relpath: str | None) -> bool:
    return backend().exists(relpath)


def delete(relpath: str | None) -> None:
    backend().delete(relpath)


def abspath(relpath: str):
    return backend().abspath(relpath)


def url(relpath: str | None) -> str | None:
    return backend().url(relpath)


def absolute_url(request, relpath: str | None) -> str | None:
    return backend().absolute_url(request, relpath)


def file_response(relpath: str, media_type: str, filename: str, inline: bool = True) -> Response:
    return backend().file_response(relpath, media_type, filename, inline)
