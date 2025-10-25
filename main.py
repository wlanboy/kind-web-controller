from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from models import SessionLocal, ClusterConfig, init_db
from utils import get_active_clusters, create_cluster, delete_cluster, render_config, detect_system, fetch_kind_versions, download_kind

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

init_db()

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    db = SessionLocal()
    configs = db.query(ClusterConfig).all()
    clusters = get_active_clusters()
    return templates.TemplateResponse("dashboard.html", {"request": request, "configs": configs, "clusters": clusters})

@app.post("/create-config", response_class=HTMLResponse)
def create_config(request: Request, name: str = Form(...), hostname: str = Form(...)):
    db = SessionLocal()
    db.add(ClusterConfig(name=name, hostname=hostname))
    db.commit()
    return templates.TemplateResponse("config_row.html", {"request": request, "config": ClusterConfig(name=name, hostname=hostname)})

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
    create_cluster(config.name)
    return templates.TemplateResponse("cluster_row.html", {"request": {}, "cluster": config.name})

@app.post("/delete-cluster", response_class=HTMLResponse)
def delete_cluster_route(name: str = Form(...)):
    delete_cluster(name)
    return HTMLResponse("")
