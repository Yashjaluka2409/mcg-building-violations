"""Command line (replaces `manage.py <command>`):

    python -m app.cli migrate                      apply Alembic migrations (creates the database)
    python -m app.cli makemigration "message"      autogenerate a new Alembic revision from the models
    python -m app.cli load-legal-catalogue         statutes / sections / violation types / order types / access defaults
    python -m app.cli seed-demo [--with-cases]     demo masters + officers (+ sample cases and planned inspections)
    python -m app.cli sweep                        run the periodic jobs once (SLA, deadlines, SMS retries) - for cron
    python -m app.cli openapi [out.json]           write the OpenAPI schema
    python -m app.cli serve [--port 8000]          development server (uvicorn, reload)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from app.core.config import BASE_DIR, settings


def _alembic_cfg():
    from alembic.config import Config
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BASE_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.sqlalchemy_url.replace("%", "%%"))
    return cfg


def migrate():
    from alembic import command
    command.upgrade(_alembic_cfg(), "head")
    print("database is at the latest migration:", settings.sqlalchemy_url.split("@")[-1])


def makemigration(message: str):
    from alembic import command
    command.revision(_alembic_cfg(), message=message, autogenerate=True)


async def _with_session(fn, *args, **kwargs):
    from app.db import session
    async with session.session_scope() as db:
        out = await db.run_sync(lambda s: fn(s, *args, **kwargs))
    await session.engine.dispose()
    return out


def load_legal_catalogue(legal_dir=None):
    from app.seed import load_legal_catalogue as fn
    out = asyncio.run(_with_session(fn, legal_dir))
    print("Loaded:", json.dumps(out, default=str))


def seed_demo(with_cases: bool):
    from app.seed import seed_demo as fn
    out = asyncio.run(_with_session(fn, with_cases=with_cases))
    print("Seeded:", json.dumps(out, default=str))
    print("Demo OTP: 123456   Logins: JE 9000000001  AE 9000000002  JC 9000000003  Clerk 9000000004  Admin 9000000009  Planning 9000000011  Revenue 9000000012  Legal 9000000013  GIS lab 9000000014")


def sweep():
    from app.services.building_violations.scheduler import run_all
    print(json.dumps(asyncio.run(_with_session(run_all)), default=str))


def openapi(out: str | None):
    from app.main import app
    text = json.dumps(app.openapi(), indent=1, ensure_ascii=False)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("written", out)
    else:
        print(text)


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m app.cli", description="MCG BVMS server commands")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate")
    mk = sub.add_parser("makemigration")
    mk.add_argument("message")
    lc = sub.add_parser("load-legal-catalogue")
    lc.add_argument("--dir", default=None)
    sd = sub.add_parser("seed-demo")
    sd.add_argument("--with-cases", action="store_true")
    sub.add_parser("sweep")
    oa = sub.add_parser("openapi")
    oa.add_argument("out", nargs="?", default=None)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    a = p.parse_args(argv)
    if a.cmd == "migrate":
        migrate()
    elif a.cmd == "makemigration":
        makemigration(a.message)
    elif a.cmd == "load-legal-catalogue":
        load_legal_catalogue(a.dir)
    elif a.cmd == "seed-demo":
        seed_demo(a.with_cases)
    elif a.cmd == "sweep":
        sweep()
    elif a.cmd == "openapi":
        openapi(a.out)
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("app.main:app", host=a.host, port=a.port, reload=True, proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    sys.exit(main())
