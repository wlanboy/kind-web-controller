from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from models import SessionLocal, ClusterConfig, init_db
from utils import (
    get_active_clusters,
    create_cluster,
    delete_cluster,
    render_config
)
import asyncio

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    configs = db.query(ClusterConfig).all()
    clusters = get_active_clusters()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "configs": configs,
        "clusters": clusters
    })

@app.get("/clusters", response_class=HTMLResponse)
def get_clusters(request: Request):
    clusters = get_active_clusters()
    return templates.TemplateResponse("cluster_table.html", {
        "request": request,
        "clusters": clusters
    })

@app.post("/create-config", response_class=HTMLResponse)
def create_config(request: Request, name: str = Form(...), hostname: str = Form(...)):
    db = SessionLocal()
    config = ClusterConfig(name=name, hostname=hostname)
    db.add(config)
    db.commit()
    return templates.TemplateResponse("config_row.html", {
        "request": request,
        "config": config
    })

@app.post("/delete-config", response_class=HTMLResponse)
def delete_config(name: str = Form(...)):
    db = SessionLocal()
    db.query(ClusterConfig).filter_by(name=name).delete()
    db.commit()
    return HTMLResponse("")

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
def delete_cluster_route(name: str = Form(...)):
    return HTMLResponse("") 

@app.get("/stream")
async def stream(task: str, name: str):
    print(f"[DEBUG] /stream called with task={task}, name={name}")
    async def event_generator():
        try:
            if task == "run":
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
