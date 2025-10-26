from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from config import KIND_BIN
import os, subprocess
import requests
import re

templates = Jinja2Templates(directory="templates")
router = APIRouter()

def get_installed_kind_version() -> str:
    try:
        result = subprocess.run([KIND_BIN, "version"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            match = re.search(r"kind v([\d\.]+)", result.stdout)
            return match.group(1) if match else "unknown"
        return "not installed"
    except Exception:
        return "error"

def fetch_kind_versions() -> list[str]:
    try:
        response = requests.get("https://api.github.com/repos/kubernetes-sigs/kind/releases")
        if response.status_code == 200:
            return [
                r["tag_name"].lstrip("v")
                for r in response.json()
                if not r.get("prerelease", False)
            ]
    except Exception:
        pass
    return []

@router.get("/kind", response_class=HTMLResponse)
def kind_page(request: Request):
    current = get_installed_kind_version()
    available = fetch_kind_versions()
    return templates.TemplateResponse("kind_admin.html", {
        "request": request,
        "current": current,
        "available": available
    })

@router.post("/install-kind")
def install_kind(version: str = Form(...)):
    url = f"https://github.com/kubernetes-sigs/kind/releases/download/v{version}/kind-linux-amd64"
    target_dir = os.path.dirname(KIND_BIN)
    os.makedirs(target_dir, exist_ok=True)

    try:
        subprocess.run(["curl", "-Lo", KIND_BIN, url], check=True)
        subprocess.run(["chmod", "+x", KIND_BIN], check=True)
        return PlainTextResponse(f"Kind {version} wurde erfolgreich installiert unter {KIND_BIN}")
    except subprocess.CalledProcessError as e:
        return PlainTextResponse(f"Fehler bei der Installation: {e}", status_code=500)
    except Exception as e:
        return PlainTextResponse(f"Unerwarteter Fehler: {e}", status_code=500)

@router.get("/check-kind-version", response_class=PlainTextResponse)
def check_kind_version():
    return get_installed_kind_version()
