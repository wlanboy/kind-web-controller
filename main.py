from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from models import SessionLocal, ClusterConfig, init_db
from config import METALLB_VERSION
from utils import (
    get_active_clusters,
    render_config,
    render_metallb_yaml,
    get_active_kind_clusters, 
    get_enriched_clusters
)
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_kind_clusters()
    active = get_enriched_clusters()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "configured": configured,
        "active": active,
        "active_names": active_names
    })

@app.get("/configs", response_class=HTMLResponse)
def get_configs(request: Request):
    db = SessionLocal()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_kind_clusters()
    return templates.TemplateResponse("config_table.html", {
        "request": request,
        "configured": configured,
        "active_names": active_names
    })

@app.get("/clusters", response_class=HTMLResponse)
def get_clusters(request: Request):
    active = get_enriched_clusters()
    return templates.TemplateResponse("cluster_table.html", {
        "request": request,
        "active": active
    })

@app.post("/refresh-cluster", response_class=HTMLResponse)
def refresh_cluster(request: Request, name: str = Form(...)):
    active = get_active_kind_clusters()
    if name not in active:
        return HTMLResponse(f"<tr><td colspan='3'>Cluster {name} not running</td></tr>")

    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    if not config:
        config = ClusterConfig(name=name, hostname="unknown", network="", metallbinstalled=False)

    return templates.TemplateResponse("cluster_row.html", {
        "request": request,
        "config": config
    })

@app.post("/create-config", response_class=HTMLResponse)
def create_config(request: Request, name: str = Form(...), hostname: str = Form(...), network: str = Form("")):
    db = SessionLocal()
    existing = db.query(ClusterConfig).filter_by(name=name).first()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_kind_clusters()

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
        "active_names": get_active_kind_clusters()
    })

@app.post("/delete-config", response_class=HTMLResponse)
def delete_config(request: Request, name: str = Form(...)):
    db = SessionLocal()
    db.query(ClusterConfig).filter_by(name=name).delete()
    db.commit()
    configured = db.query(ClusterConfig).all()
    active_names = get_active_kind_clusters()
    return templates.TemplateResponse("config_table.html", {
        "request": request,
        "configured": configured,
        "active_names": active_names
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
                cmd = ["kind", "create", "cluster", "--name", name, "--config", f"./{name}.conf"]
            elif task == "delete":
                cmd = ["kind", "delete", "clusters", name]
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

@app.post("/install-metallb", response_class=HTMLResponse)
def install_metallb(name: str = Form(...)):
    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    if not config or not config.network:
        return HTMLResponse("")

    render_metallb_yaml(config.name, config.network)
    return HTMLResponse("")  # Button löst nur Stream aus

@app.get("/streammetallb")
async def stream_metallb(name: str):
    METALLB_VERSION = "0.15.2"
    async def event_generator():
        returncodes = []
        try:
            cmds = [
                ["kubectl", "--context", f"kind-{name}", "apply", "-f", f"https://raw.githubusercontent.com/metallb/metallb/v{METALLB_VERSION}/config/manifests/metallb-native.yaml"],
                ["kubectl", "--context", f"kind-{name}", "wait", "--for=condition=ready", "pod", "--all", "-n", "metallb-system", "--timeout=300s"],
                ["kubectl", "--context", f"kind-{name}", "apply", "-f", f"metallb-{name}.yaml"]
            ]

            for cmd in cmds:
                yield f"data: Running: {' '.join(cmd)}\n\n"
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT
                )
                
                while True:
                    line = await process.stdout.readline()
                    if not line:
                        break
                    yield f"data: {line.decode().rstrip()}\n\n"
                await process.wait()
                returncodes.append(process.returncode)

                if all(returncode == 0 for returncode in returncodes):
                    db = SessionLocal()
                    config = db.query(ClusterConfig).filter_by(name=name).first()
                    config.metallbinstalled = True
                    db.commit()

                yield f"data: Done with exit code {process.returncode}\n\n"
                yield f"data: [STREAM CLOSED]\n\n"

        except Exception as e:
            yield f"data: [EXCEPTION] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
