import subprocess, os, platform, requests, re
from jinja2 import Environment, FileSystemLoader
from models import SessionLocal, ClusterConfig
from config import KIND_BIN

def get_active_clusters():
    if not os.path.isfile(KIND_BIN) or not os.access(KIND_BIN, os.X_OK):
        return []  # Kind nicht installiert → keine Cluster
    try:
        result = subprocess.run([KIND_BIN, "get", "clusters"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    return []

def create_cluster(name):
    subprocess.run([KIND_BIN, "create", "cluster", "--name", name, "--config", f"./{name}.conf"])

def delete_cluster(name):
    subprocess.run([KIND_BIN, "delete", "clusters", name])

def render_config(name, hostname):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("cluster_template.yaml.j2")
    config = template.render(name=name, hostname=hostname)
    with open(f"{name}.conf", "w") as f:
        f.write(config)

def detect_system():
    os_name = platform.system().lower()
    arch = platform.machine().lower()
    if arch == "x86_64": arch = "amd64"
    elif arch == "aarch64": arch = "arm64"
    return os_name, arch

def is_kind_installed() -> bool:
    return os.path.isfile(KIND_BIN) and os.access(KIND_BIN, os.X_OK)

def render_metallb_yaml(name: str, network: str):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("metallb.yaml.j2")
    rendered = template.render(network=network)
    with open(f"metallb-{name}.yaml", "w") as f:
        f.write(rendered)

def get_enriched_clusters() -> list[ClusterConfig]:
    active = get_active_clusters()
    db = SessionLocal()
    configs = db.query(ClusterConfig).filter(ClusterConfig.name.in_(active)).all()
    config_map = {c.name: c for c in configs}

    enriched = []
    for name in active:
        config = config_map.get(name)
        if config:
            enriched.append(config)
        else:
            enriched.append(ClusterConfig(name=name, hostname="unknown", network="", metallbinstalled=False))
    return enriched

def is_metallb_installed(cluster_name: str) -> bool:
    try:
        result = subprocess.run(
            ["kubectl", "--context", f"kind-{cluster_name}", "get", "deployment", "controller", "-n", "metallb-system"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def is_istio_installed(cluster_name: str) -> bool:
    try:
        result = subprocess.run(
            ["kubectl", "--context", f"kind-{cluster_name}", "get", "deployment", "istiod", "-n", "istio-system"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False
