"""
OpenFPD policy submission web app.

Run:
    .venv-web/bin/uvicorn web.app:app --reload --port 8000
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SUBMISSIONS_DIR = BASE_DIR.parent / "data" / "submissions"
SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# ---------------------------------------------------------------------------
# Sanitization
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]*>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[ \t]+")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _sanitize(value: str | None, max_len: int = 2000) -> str:
    if value is None:
        return ""
    s = _TAG_RE.sub("", value)
    s = _CONTROL_RE.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _MULTI_SPACE.sub(" ", s)
    s = "\n".join(line.strip() for line in s.splitlines())
    return s[:max_len].strip()


def _sanitize_url(value: str | None) -> str:
    if not value:
        return ""
    s = _sanitize(value, max_len=500).strip()
    if re.match(r"^https?://", s, re.IGNORECASE):
        return s
    return ""


def _sanitize_year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        y = int(value)
        return y if 1800 <= y <= 2100 else None
    except ValueError:
        return None


def _sanitize_choice(value: str | None, allowed: list[str]) -> str:
    if value and value in allowed:
        return value
    return ""


# ---------------------------------------------------------------------------
# Allowed values for dropdowns
# ---------------------------------------------------------------------------

POLICY_DIRECTIONS = [
    "", "Strategy", "Plan", "Policy", "Law", "Regulation",
    "Programme", "Action Plan", "Framework", "Guidelines",
    "Decree", "Order", "Agreement", "Other",
]
FOOD_SEC_DIMS = [
    "", "Availability", "Access", "Utilization",
    "Stability", "Multiple", "Not specified",
]
TERMS = ["", "Short", "Medium", "Long"]
YES_NO = ["", "Y", "N"]

_FORM_CONTEXT = {
    "policy_directions": POLICY_DIRECTIONS,
    "food_sec_dims": FOOD_SEC_DIMS,
    "terms": TERMS,
    "yes_no": YES_NO,
}

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="OpenFPD Policy Submission")


@app.get("/", response_class=HTMLResponse)
async def form_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "submit.html", {
        **_FORM_CONTEXT,
        "error": None,
        "prev": None,
    })


@app.post("/submit")
async def handle_submit(
    request: Request,
    submitter_name:  Annotated[str, Form()] = "",
    submitter_email: Annotated[str, Form()] = "",
    country:                  Annotated[str, Form()] = "",
    policy_description:       Annotated[str, Form()] = "",
    policydecision_details:   Annotated[str, Form()] = "",
    y_start:  Annotated[str, Form()] = "",
    y_end:    Annotated[str, Form()] = "",
    policydirection:    Annotated[str, Form()] = "",
    policycategory:     Annotated[str, Form()] = "",
    policycategorycode: Annotated[str, Form()] = "",
    contextoradditionalinfo:      Annotated[str, Form()] = "",
    decision_making_institution:  Annotated[str, Form()] = "",
    term:                  Annotated[str, Form()] = "",
    targeted:              Annotated[str, Form()] = "",
    emergency:             Annotated[str, Form()] = "",
    foodsecuritydimension: Annotated[str, Form()] = "",
    commodity1: Annotated[str, Form()] = "",
    commodity2: Annotated[str, Form()] = "",
    commodity3: Annotated[str, Form()] = "",
    source1name: Annotated[str, Form()] = "",
    source1link: Annotated[str, Form()] = "",
    url:         Annotated[str, Form()] = "",
    topics: Annotated[str, Form()] = "",
) -> HTMLResponse:

    data = {
        "submitter_name":  _sanitize(submitter_name, 150),
        "submitter_email": _sanitize(submitter_email, 200),
        "country":                  _sanitize(country, 100),
        "policy_description":       _sanitize(policy_description, 500),
        "policydecision_details":   _sanitize(policydecision_details, 5000),
        "y_start":                  _sanitize_year(y_start),
        "y_end":                    _sanitize_year(y_end),
        "policydirection":          _sanitize_choice(policydirection, POLICY_DIRECTIONS),
        "policycategory":           _sanitize(policycategory, 300),
        "policycategorycode":       _sanitize(policycategorycode, 50),
        "contextoradditionalinfo":  _sanitize(contextoradditionalinfo, 3000),
        "decision_making_institution": _sanitize(decision_making_institution, 300),
        "term":                  _sanitize_choice(term, TERMS),
        "targeted":              _sanitize_choice(targeted, YES_NO),
        "emergency":             _sanitize_choice(emergency, YES_NO),
        "foodsecuritydimension": _sanitize_choice(foodsecuritydimension, FOOD_SEC_DIMS),
        "commodity1": _sanitize(commodity1, 100),
        "commodity2": _sanitize(commodity2, 100),
        "commodity3": _sanitize(commodity3, 100),
        "source1name": _sanitize(source1name, 200),
        "source1link": _sanitize_url(source1link),
        "url":         _sanitize_url(url),
        "topics":      _sanitize(topics, 500),
    }

    errors: list[str] = []
    if not data["submitter_name"]:
        errors.append("Your name is required.")
    if not data["submitter_email"]:
        errors.append("Your e-mail is required.")
    elif not _EMAIL_RE.match(data["submitter_email"]):
        errors.append("Please enter a valid e-mail address.")
    if not data["country"]:
        errors.append("Country is required.")
    if not data["policy_description"]:
        errors.append("Policy title is required.")
    if not data["policydecision_details"]:
        errors.append("Policy description is required.")
    if data["y_start"] and data["y_end"] and data["y_start"] > data["y_end"]:
        errors.append("Start year cannot be after end year.")

    if errors:
        return templates.TemplateResponse(
            request,
            "submit.html",
            {
                **_FORM_CONTEXT,
                "error": " ".join(errors),
                "prev": data,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    submission = {
        "submission_id":  str(uuid.uuid4()),
        "submitted_at":   datetime.now(timezone.utc).isoformat(),
        "status":         "pending_review",
        "submitter": {
            "name":  data.pop("submitter_name"),
            "email": data.pop("submitter_email"),
        },
        "policy": {k: v for k, v in data.items() if v not in (None, "")},
    }

    fname = f"{submission['submitted_at'][:10]}_{submission['submission_id'][:8]}.json"
    (SUBMISSIONS_DIR / fname).write_text(
        json.dumps(submission, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return RedirectResponse(
        url=f"/thank-you?id={submission['submission_id']}"
            f"&country={submission['policy'].get('country', '')}"
            f"&title={submission['policy'].get('policy_description', '')}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@app.get("/thank-you", response_class=HTMLResponse)
async def thank_you(
    request: Request,
    id: str = "",
    country: str = "",
    title: str = "",
) -> HTMLResponse:
    return templates.TemplateResponse(request, "success.html", {
        "submission_id": _sanitize(id, 36),
        "country": _sanitize(country, 100),
        "title":   _sanitize(title, 500),
    })
