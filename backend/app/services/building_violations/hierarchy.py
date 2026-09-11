"""
Configurable review hierarchy - who reports, who reviews, who decides.

* ROLES  - table `bvms_role`: the role catalogue (code, English / Hindi label, short label, kind). The admin
           can rename a role ("Building Inspector" instead of "Junior Engineer") or add a new code
           ("SUPERVISOR"); officers, workflow rules and permissions refer to the code.
* STAGES - table `bvms_review_stage`: the ordered chain a case travels through - exactly one REPORTER stage
           (records the inspection), zero or more REVIEWER stages (review / forward / return) and exactly one
           AUTHORITY stage (the competent authority who issues notices and orders). Default: JE -> AE -> JC.

The state machine keeps its status codes (PENDING_AE = "under review", PENDING_JC = "with the authority",
RETURNED_TO_JE = "returned to the reporter" ...) so the hash-chained audit trail stays readable;
`ViolationCase.review_stage` records which reviewer stage a case is at. Every label the portal and the app
show is derived here from the current configuration (`client_config`), and a role that fills a stage inherits
the workflow rules, permissions and jurisdiction scoping of the slot's canonical role (JE / AE / JC) until the
admin refines them - so a renamed or newly created role works everywhere at once.

Cached for 30 s per process; `invalidate()` is called on every admin write.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.building_violations import STATUS_LABELS, CaseStatus as S, OfficerProfile, ReviewStage, Role, RoleDef

SLOTS = ("REPORTER", "REVIEWER", "AUTHORITY")
CANONICAL = {"REPORTER": Role.JE, "REVIEWER": Role.AE, "AUTHORITY": Role.JC}
KINDS = ("CHAIN", "SUPPORT", "MANAGEMENT")
SLOT_LABELS = {"REPORTER": "Reports the inspection", "REVIEWER": "Reviews and forwards / returns", "AUTHORITY": "Competent authority - issues notices and orders"}

# code, label_en, label_hi, short_label, kind, sort_order
DEFAULT_ROLES = [
    ("JE", "Junior Engineer", "कनिष्ठ अभियंता", "JE", "CHAIN", 10),
    ("AE", "Assistant Engineer", "सहायक अभियंता", "AE", "CHAIN", 20),
    ("XEN", "Executive Engineer", "कार्यकारी अभियंता", "XEN", "SUPPORT", 30),
    ("JC", "Joint Commissioner", "संयुक्त आयुक्त", "JC", "CHAIN", 40),
    ("JC_CLERK", "Office clerk of the competent authority (uploads replies)", "सक्षम प्राधिकारी कार्यालय लिपिक", "Clerk", "SUPPORT", 50),
    ("ADDL_COMMISSIONER", "Additional Commissioner", "अतिरिक्त आयुक्त", "Addl. Comm.", "MANAGEMENT", 60),
    ("COMMISSIONER", "Commissioner", "आयुक्त", "Comm.", "MANAGEMENT", 70),
    ("FIELD_STAFF", "Enforcement / demolition squad", "प्रवर्तन दल", "Field", "SUPPORT", 80),
    ("BRANCH_OFFICER", "Branch officer (Planning / Revenue / Legal ...) - consulted on cases", "शाखा अधिकारी", "Branch", "SUPPORT", 90),
    ("GIS_LAB", "GIS lab - maintains government-land and ward layers", "जीआईएस लैब", "GIS", "SUPPORT", 100),
    ("ADMIN", "Module administrator", "प्रशासक", "Admin", "MANAGEMENT", 110),
    ("VIEWER", "Read-only (MIS)", "केवल-पठन (MIS)", "Viewer", "SUPPORT", 120),
]
# slot, role, label_en, label_hi
DEFAULT_STAGES = [("REPORTER", "JE", "Junior Engineer", "कनिष्ठ अभियंता"), ("REVIEWER", "AE", "Assistant Engineer", "सहायक अभियंता"), ("AUTHORITY", "JC", "Joint Commissioner", "संयुक्त आयुक्त")]
ROLE_CODE = re.compile(r"[A-Z][A-Z0-9_]{1,23}")


@dataclass(frozen=True)
class Stage:
    position: int
    slot: str
    role: str
    label_en: str
    label_hi: str

    @property
    def canonical(self) -> str:
        return CANONICAL[self.slot]

    def label(self, lang: str = "en") -> str:
        return self.label_hi if lang == "hi" and self.label_hi else self.label_en

    def as_dict(self) -> dict:
        return {"position": self.position, "slot": self.slot, "role": self.role, "label_en": self.label_en, "label_hi": self.label_hi, "canonical": self.canonical}


_cache: dict = {"roles": None, "stages": None, "at": 0.0}
TTL = 30.0


def invalidate():
    _cache.update({"roles": None, "stages": None, "at": 0.0})


def _fresh():
    if time.time() - _cache["at"] > TTL:
        invalidate()
        _cache["at"] = time.time()


def _default_roles() -> list[dict]:
    return [{"code": c, "label_en": en, "label_hi": hi, "short_label": sh, "kind": k, "sort_order": o, "active": True, "builtin": True} for c, en, hi, sh, k, o in DEFAULT_ROLES]


def _default_stages() -> list[Stage]:
    return [Stage(i + 1, slot, role, en, hi) for i, (slot, role, en, hi) in enumerate(DEFAULT_STAGES)]


# ---------------------------------------------------------------- roles
def roles(db: Session | None) -> list[dict]:
    """All roles (active and inactive) in display order. Without a session the cached / default list is used."""
    _fresh()
    if _cache["roles"] is None:
        if db is None:
            return _default_roles()
        rows = db.query(RoleDef).order_by(RoleDef.sort_order, RoleDef.code).all()
        _cache["roles"] = ([{"code": r.code, "label_en": r.label_en, "label_hi": r.label_hi, "short_label": r.short_label or r.code, "kind": r.kind, "sort_order": r.sort_order,
                             "active": r.active, "builtin": r.builtin} for r in rows] if rows else _default_roles())
    return _cache["roles"]


def role_map(db: Session | None) -> dict[str, dict]:
    return {r["code"]: r for r in roles(db)}


def role_codes(db: Session | None, active_only: bool = True) -> list[str]:
    return [r["code"] for r in roles(db) if r["active"] or not active_only]


def role_labels(db: Session | None, lang: str = "en") -> dict[str, str]:
    return {r["code"]: (r["label_hi"] if lang == "hi" and r["label_hi"] else r["label_en"]) for r in roles(db)}


def role_label(db: Session | None, code: str | None, lang: str = "en") -> str:
    if not code:
        return ""
    r = role_map(db).get(code)
    if not r:
        return code
    return r["label_hi"] if lang == "hi" and r["label_hi"] else r["label_en"]


def role_short(db: Session | None, code: str | None) -> str:
    r = role_map(db).get(code or "")
    return (r["short_label"] if r else code) or (code or "")


# ---------------------------------------------------------------- stages
def chain(db: Session | None) -> list[Stage]:
    _fresh()
    if _cache["stages"] is None:
        if db is None:
            return _default_stages()
        rows = db.query(ReviewStage).filter(ReviewStage.active == True).order_by(ReviewStage.position, ReviewStage.id).all()  # noqa: E712
        _cache["stages"] = [Stage(i + 1, r.slot, r.role, r.label_en, r.label_hi or "") for i, r in enumerate(rows)] if rows else _default_stages()
    return _cache["stages"]


def reporter(db) -> Stage:
    return next((s for s in chain(db) if s.slot == "REPORTER"), _default_stages()[0])


def authority(db) -> Stage:
    return next((s for s in chain(db) if s.slot == "AUTHORITY"), _default_stages()[-1])


def reviewers(db, raw: bool = False) -> list[Stage]:
    """Reviewer stages in order. The routing switch `require_ae_review` (Administration > Routing) still works:
    when it is off the chain behaves as if it had no reviewer stage. `raw=True` ignores the switch."""
    revs = [s for s in chain(db) if s.slot == "REVIEWER"]
    if raw or db is None:
        return revs
    from app.services.building_violations import access  # local import: access imports this module
    return revs if access.get_setting(db, "require_ae_review", True) else []


def reporter_role(db) -> str:
    return reporter(db).role


def authority_role(db) -> str:
    return authority(db).role


def slot_roles(db, slot: str) -> list[str]:
    out = [s.role for s in chain(db) if s.slot == slot]
    return out or [CANONICAL[slot]]


def stage_of_role(db, role: str | None) -> Stage | None:
    return next((s for s in chain(db) if s.role == role), None)


def slot_of_role(db, role: str | None) -> str | None:
    st = stage_of_role(db, role)
    return st.slot if st else None


def canonical_role(db, role: str | None) -> str | None:
    """The built-in role whose rules / permissions / scoping a role inherits: JE for the reporter stage, AE for
    a reviewer stage, JC for the authority stage; any other role is its own canonical role."""
    st = stage_of_role(db, role)
    return st.canonical if st else role


def lookup_roles(db, role: str | None) -> list[str]:
    c = canonical_role(db, role)
    return [role] if c == role or c is None else [role, c]


def current_stage(db, case) -> Stage | None:
    """The stage a case is at right now (for labels and for the 'only the current stage may act' guard)."""
    st = case.status
    if st in (S.PENDING_AE, S.RESPONSE_PENDING_AE):
        revs = reviewers(db, raw=True)
        if not revs:
            return None
        idx = max((case.review_stage or 1) - 1, 0)
        return revs[idx] if idx < len(revs) else revs[-1]
    if st in (S.DRAFT, S.RETURNED_TO_JE):
        return reporter(db)
    if st in (S.PENDING_JC, S.RESPONSE_PENDING_JC, S.RESPONSE_RECEIVED, S.NO_RESPONSE, S.HEARING_SCHEDULED):
        return authority(db)
    return None


def next_stage(db, case) -> Stage:
    """Where a forward from the case's current position goes."""
    revs = reviewers(db)
    if case is not None and case.status in (S.PENDING_AE, S.RESPONSE_PENDING_AE):
        idx = case.review_stage or 1
        return revs[idx] if idx < len(revs) else authority(db)
    return revs[0] if revs else authority(db)


# ---------------------------------------------------------------- labels
_HI = {"pending": "{x} के पास लंबित", "returned": "{x} को पुनः निरीक्षण हेतु लौटाया", "reply_pending": "उत्तर {x} के पास",
       "submit": "{x} को भेजें", "forward": "{x} को अग्रेषित करें", "return": "{x} को लौटाएँ", "forward_reply": "टिप्पणी सहित उत्तर {x} को अग्रेषित करें", "draft": "प्रारूप ({x})"}


def status_label(db, code: str, lang: str = "en", stage: Stage | None = None) -> str | None:
    """Label of a status under the current hierarchy. Returns None for statuses that do not name a stage
    (the clients keep their own bilingual labels for those)."""
    rep, auth = reporter(db), authority(db)
    revs = reviewers(db, raw=True)
    hi = lang == "hi"
    if code == S.PENDING_AE:
        s = stage or (revs[0] if revs else None)
        if not s:
            return None
        return _HI["pending"].format(x=s.label("hi")) if hi else f"Pending with {s.label_en}"
    if code == S.RESPONSE_PENDING_AE:
        s = stage or (revs[0] if revs else None)
        if not s:
            return None
        return _HI["reply_pending"].format(x=s.label("hi")) if hi else f"Reply with {s.label_en} for comments"
    if code == S.PENDING_JC:
        return _HI["pending"].format(x=auth.label("hi")) if hi else f"Pending with {auth.label_en}"
    if code == S.RESPONSE_PENDING_JC:
        return _HI["reply_pending"].format(x=auth.label("hi")) if hi else f"Reply with {auth.label_en} for decision"
    if code == S.RETURNED_TO_JE:
        return _HI["returned"].format(x=rep.label("hi")) if hi else f"Returned to {rep.label_en} for re-inspection"
    if code == S.DRAFT:
        return _HI["draft"].format(x=rep.label("hi")) if hi else f"Draft ({rep.label_en})"
    return None


def case_status_label(db, case, lang: str = "en") -> str:
    lab = status_label(db, case.status, lang, stage=current_stage(db, case) if case.status in (S.PENDING_AE, S.RESPONSE_PENDING_AE) else None)
    if lab:
        return lab
    return STATUS_LABELS.get(case.status, case.status) if lang == "en" else (STATUS_LABELS.get(case.status) or case.status)


def action_label(db, code: str, lang: str = "en", case=None) -> str | None:
    """Label of a workflow action under the current hierarchy (None = use the generic label)."""
    hi = lang == "hi"
    if code == "submit_to_ae":
        nxt = next_stage(db, None)
        return _HI["submit"].format(x=nxt.label("hi")) if hi else f"Submit to {nxt.label_en}"
    if code == "ae_forward":
        nxt = next_stage(db, case)
        return _HI["forward"].format(x=nxt.label("hi")) if hi else f"Forward to {nxt.label_en}"
    if code == "ae_return":
        rep = reporter(db)
        return _HI["return"].format(x=rep.label("hi")) if hi else f"Return to {rep.label_en}"
    if code == "ae_forward_response":
        nxt = next_stage(db, case)
        return _HI["forward_reply"].format(x=nxt.label("hi")) if hi else f"Comment & forward reply to {nxt.label_en}"
    return None


def client_config(db: Session) -> dict:
    """Everything the portal and the app need to render the hierarchy: roles with labels, the stage chain,
    status and action labels in English and Hindi."""
    from app.services.building_violations import access
    stages = chain(db)
    rm = role_map(db)
    statuses = {}
    for code, en in S.choices:
        statuses[code] = {"label_en": status_label(db, code, "en") or en, "label_hi": status_label(db, code, "hi")}
    actions = {}
    for code, en in access.ACTION_LABELS.items():
        actions[code] = {"label_en": action_label(db, code, "en") or en, "label_hi": action_label(db, code, "hi")}
    rev = reviewers(db)
    return {
        "roles": [{**r, "slot": slot_of_role(db, r["code"]), "inherits": (canonical_role(db, r["code"]) if canonical_role(db, r["code"]) != r["code"] else None)} for r in roles(db)],
        "stages": [{**s.as_dict(), "short_label": role_short(db, s.role), "role_label_en": role_label(db, s.role), "role_label_hi": role_label(db, s.role, "hi")} for s in stages],
        "slots": {"REPORTER": reporter(db).as_dict(), "REVIEWER": [s.as_dict() for s in rev], "AUTHORITY": authority(db).as_dict()},
        "slot_labels": SLOT_LABELS, "review_enabled": bool(rev),
        "statuses": statuses, "actions": actions,
        "management_roles": list(access.MANAGEMENT_ROLES), "canonical": CANONICAL,
        "summary": " → ".join(s.label_en for s in [reporter(db), *rev, authority(db)]),
        "role_labels": {c: rm[c]["label_en"] for c in rm},
    }


# ---------------------------------------------------------------- seeding and admin writes
def seed(db: Session) -> int:
    """Create the default role catalogue and the JE -> AE -> JC chain where missing (idempotent)."""
    n = 0
    have = {r.code for r in db.query(RoleDef).all()}
    for code, en, hi, sh, kind, order in DEFAULT_ROLES:
        if code not in have:
            db.add(RoleDef(code=code, label_en=en, label_hi=hi, short_label=sh, kind=kind, sort_order=order, active=True, builtin=True))
            n += 1
    if not db.query(ReviewStage.id).first():
        for i, (slot, role, en, hi) in enumerate(DEFAULT_STAGES, 1):
            db.add(ReviewStage(position=i, slot=slot, role=role, label_en=en, label_hi=hi, active=True))
            n += 1
    db.flush()
    invalidate()
    return n


def save(db: Session, *, stages: list[dict], roles_in: list[dict] | None = None, actor=None) -> None:
    """Validate and store a new hierarchy (roles first, then the stage chain). Raises ValueError (-> HTTP 400)."""
    seed(db)
    uid = getattr(actor, "id", None)
    existing = {r.code: r for r in db.query(RoleDef).all()}
    stage_roles = [str(s.get("role") or "").strip().upper() for s in stages or []]
    for r in roles_in or []:
        code = str(r.get("code") or "").strip().upper()
        if not ROLE_CODE.fullmatch(code):
            raise ValueError(f'Invalid role code "{code}": use capital letters, digits and underscore (2-24 characters)')
        label = (r.get("label_en") or "").strip()
        if not label:
            raise ValueError(f"Role {code}: the English label is required")
        kind = r.get("kind") or "SUPPORT"
        if kind not in KINDS:
            raise ValueError(f"Role {code}: kind must be one of {', '.join(KINDS)}")
        row = existing.get(code)
        if row is None:
            row = RoleDef(code=code, builtin=False, sort_order=int(r.get("sort_order") or 200))
            db.add(row)
            existing[code] = row
        if row.builtin and row.kind == "MANAGEMENT":
            kind = "MANAGEMENT"      # the management roles are fixed in code (access.MANAGEMENT_ROLES)
        active = bool(r.get("active", True))
        if not active and code in stage_roles:
            raise ValueError(f"Role {code} is used by a review stage and cannot be deactivated")
        if not active and db.query(OfficerProfile.id).filter(OfficerProfile.role == code, OfficerProfile.active == True).first():  # noqa: E712
            raise ValueError(f"Role {code} still has active officers; move them to another role first")
        row.label_en, row.label_hi, row.short_label = label[:120], (r.get("label_hi") or "").strip()[:120], ((r.get("short_label") or "").strip() or code[:8])[:24]
        row.kind, row.active, row.updated_by_id = kind, active, uid
        if r.get("sort_order") is not None:
            try:
                row.sort_order = int(r["sort_order"])
            except (TypeError, ValueError):
                pass
    db.flush()
    if not stages:
        raise ValueError("At least a reporter stage and an authority stage are required")
    slots = [str(s.get("slot") or "") for s in stages]
    if slots[0] != "REPORTER" or slots[-1] != "AUTHORITY" or slots.count("REPORTER") != 1 or slots.count("AUTHORITY") != 1 or any(x != "REVIEWER" for x in slots[1:-1]):
        raise ValueError("The chain must start with one reporter stage, end with one authority stage and have only reviewer stages in between")
    active_codes = {c for c, r in existing.items() if r.active}
    seen: set[str] = set()
    for s, role in zip(stages, stage_roles):
        if role not in active_codes:
            raise ValueError(f'Stage role "{role}" is not an active role')
        if role in seen:
            raise ValueError(f"Role {role} appears in more than one stage")
        seen.add(role)
        if not (s.get("label_en") or "").strip():
            raise ValueError("Every stage needs an English label")
    db.query(ReviewStage).delete(synchronize_session=False)
    for i, (s, role) in enumerate(zip(stages, stage_roles), 1):
        db.add(ReviewStage(position=i, slot=s["slot"], role=role, label_en=s["label_en"].strip()[:120], label_hi=(s.get("label_hi") or "").strip()[:120], active=True, updated_by_id=uid))
        if existing[role].kind != "MANAGEMENT":
            existing[role].kind = "CHAIN"
    db.flush()
    invalidate()


def reset(db: Session) -> None:
    """Back to the shipped catalogue and the JE -> AE -> JC chain (custom roles without officers are removed)."""
    db.query(ReviewStage).delete(synchronize_session=False)
    for r in db.query(RoleDef).all():
        if not r.builtin and not db.query(OfficerProfile.id).filter(OfficerProfile.role == r.code).first():
            db.delete(r)
    db.flush()
    defaults = {c: (en, hi, sh, k, o) for c, en, hi, sh, k, o in DEFAULT_ROLES}
    for r in db.query(RoleDef).all():
        if r.code in defaults:
            r.label_en, r.label_hi, r.short_label, r.kind, r.sort_order, r.active = defaults[r.code]
    db.flush()
    invalidate()
    seed(db)


def admin_payload(db: Session) -> dict:
    seed(db)
    invalidate()
    cfg = client_config(db)
    cfg["slots_allowed"] = list(SLOTS)
    cfg["kinds"] = list(KINDS)
    return cfg
