import subprocess, os, platform, requests
from jinja2 import Environment, FileSystemLoader
from models import SessionLocal, ClusterConfig

def get_active_clusters():
    result = subprocess.run(["kind", "get", "clusters"], capture_output=True, text=True)
    return result.stdout.strip().splitlines()

def create_cluster(name):
    subprocess.run(["kind", "create", "cluster", "--name", name, "--config", f"./{name}.conf"])

def delete_cluster(name):
    subprocess.run(["kind", "delete", "clusters", name])

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

def fetch_kind_versions():
    url = "https://api.github.com/repos/kubernetes-sigs/kind/releases"
    return [r["tag_name"] for r in requests.get(url).json()[:1]]

def download_kind(version, os_name, arch):
    url = f"https://github.com/kubernetes-sigs/kind/releases/download/{version}/kind-{os_name}-{arch}"
    path = f"./bin/kind-{version}"
    os.makedirs("bin", exist_ok=True)
    with open(path, "wb") as f:
        f.write(requests.get(url).content)
    os.chmod(path, 0o755)
    return path

def render_metallb_yaml(name: str, network: str):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("metallb.yaml.j2")
    rendered = template.render(network=network)
    with open(f"metallb-{name}.yaml", "w") as f:
        f.write(rendered)

def get_active_kind_clusters() -> list[str]:
    result = subprocess.run(["kind", "get", "clusters"], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return result.stdout.strip().splitlines()

def get_enriched_clusters() -> list[ClusterConfig]:
    active = get_active_kind_clusters()
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
