from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from models import SessionLocal, ClusterConfig, init_db
from config import KIND_BIN
from kind_routes import router as kind_router
from plugins_routes import router as plugins_router
from utils import (
    render_config,
    get_active_clusters, 
    get_enriched_clusters,
    is_metallb_installed, 
    is_istio_installed,
    is_kind_installed
)
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
app.include_router(plugins_router)
app.include_router(kind_router)

init_db()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    theme = request.query_params.get("theme", "dark")
    db = SessionLocal()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_clusters()
    active = get_enriched_clusters()
    kind_installed = is_kind_installed()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "configured": configured,
        "active": active,
        "active_names": active_names,
        "kind_installed": kind_installed,
        "kind_path": KIND_BIN,
        "theme": theme
    })

@app.get("/configs", response_class=HTMLResponse)
def get_configs(request: Request):
    db = SessionLocal()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_clusters()
    return templates.TemplateResponse("config_table.html", {
        "request": request,
        "configured": configured,
        "active_names": active_names
    })

@app.get("/clusters", response_class=HTMLResponse)
def get_clusters(request: Request):
    db = SessionLocal()
    active_names = get_active_clusters()
    active = []

    for name in active_names:
        config = db.query(ClusterConfig).filter_by(name=name).first()
        if config:
            # Prüfe MetalLB
            metallb = is_metallb_installed(name)
            if config.metallbinstalled != metallb:
                config.metallbinstalled = metallb

            # Prüfe Istio
            istio = is_istio_installed(name)
            if config.istioinstalled != istio:
                config.istioinstalled = istio

            db.commit()
            active.append(config)

    return templates.TemplateResponse("cluster_table.html", {
        "request": request,
        "active": active
    })

@app.post("/create-config", response_class=HTMLResponse)
def create_config(request: Request, name: str = Form(...), hostname: str = Form(...), network: str = Form("")):
    db = SessionLocal()
    existing = db.query(ClusterConfig).filter_by(name=name).first()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_clusters()

    if existing:
        return templates.TemplateResponse("config_feedback.html", {
            "request": request,
            "message": f"Cluster '{name}' already exists.",
            "configured": configured,
            "active_names": active_names
        })

    config = ClusterConfig(name=name, hostname=hostname, network=network, metallbinstalled=False)
    db.add(config)
    db.commit()

    # Erfolgreich → nur Tabelle zurückgeben
    return templates.TemplateResponse("config_table.html", {
        "request": request,
        "configured": db.query(ClusterConfig).all(),
        "active_names": get_active_clusters()
    })

@app.post("/delete-config", response_class=HTMLResponse)
def delete_config(request: Request, name: str = Form(...)):
    db = SessionLocal()
    db.query(ClusterConfig).filter_by(name=name).delete()
    db.commit()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_clusters()
    return templates.TemplateResponse("config_table.html", {
        "request": request,
        "configured": configured,
        "active_names": active_names
    })

@app.post("/refresh-cluster", response_class=HTMLResponse)
def refresh_cluster(request: Request, name: str = Form(...)):
    active = get_active_clusters()
    if name not in active:
        return HTMLResponse(f"<tr><td colspan='3'>Cluster {name} not running</td></tr>")

    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    if config:
        # Prüfe MetalLB
        metallb = is_metallb_installed(name)
        if config.metallbinstalled != metallb:
            config.metallbinstalled = metallb

        # Prüfe Istio
        istio = is_istio_installed(name)
        if config.istioinstalled != istio:
            config.istioinstalled = istio

        db.commit()
    if not config:
        config = ClusterConfig(name=name, hostname="unknown", network="", metallbinstalled=False)

    return templates.TemplateResponse("cluster_row.html", {
        "request": request,
        "config": config
    })

@app.post("/run-cluster", response_class=HTMLResponse)
def run_cluster(name: str = Form(...)):
    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    render_config(config.name, config.hostname)
    return templates.TemplateResponse("cluster_row.html", {
        "request": {},
        "cluster": config.name
    })

@app.post("/delete-cluster", response_class=HTMLResponse)
def delete_cluster(request: Request, name: str = Form(...)):
    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    if config:
        config.metallbinstalled = False
        db.commit()
    active = get_enriched_clusters()
    return templates.TemplateResponse("cluster_table.html", {
        "request": request,
        "active": active
    })

@app.get("/stream")
async def stream(task: str, name: str):
    print(f"[DEBUG] /stream called with task={task}, name={name}")
    async def event_generator():
        try:
            if task == "run" or task == "create":
                db = SessionLocal()
                config = db.query(ClusterConfig).filter_by(name=name).first()
                render_config(config.name, config.hostname)
                cmd = [KIND_BIN, "create", "cluster", "--name", name, "--config", f"./{name}.conf"]
            elif task == "delete":
                cmd = [KIND_BIN, "delete", "clusters", name]
            else:
                print(f"[DEBUG] Unknown task: {task}")
                yield f"data: Unknown task\n\n"
                return

            print(f"[DEBUG] Starting stream for task '{task}' with command: {' '.join(cmd)}")

            yield f"data: Running: {' '.join(cmd)}\n\n"

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )

            if process.stdout is None:
                print("[DEBUG] No stdout available from subprocess")
                yield f"data: [ERROR] No stdout available\n\n"
                return

            while True:
                line = await process.stdout.readline()
                if not line:
                    break
                decoded = line.decode().rstrip()
                print(f"[DEBUG] Output: {decoded}")
                yield f"data: {decoded}\n\n"

            returncode = await process.wait()
            print(f"[DEBUG] Process finished with exit code {returncode}")
            yield f"data: Done with exit code {returncode}\n\n"
            yield f"data: [STREAM CLOSED]\n\n"

        except Exception as e:
            print(f"[DEBUG] Exception in stream: {e}")
            yield f"data: [EXCEPTION] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
