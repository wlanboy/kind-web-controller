import subprocess, os, platform, requests
from jinja2 import Environment, FileSystemLoader

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
