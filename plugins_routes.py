from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from models import SessionLocal, ClusterConfig
import asyncio

from config import (
    ISTIO_SYSTEM_NAMESPACE,
    MESH_ID,
    MESH_NETWORK,
    ISTIO_VERSION,
    METALLB_VERSION
)

from utils import (
    render_metallb_yaml,
)

router = APIRouter()

@router.post("/install-metallb", response_class=HTMLResponse)
def install_metallb(name: str = Form(...)):
    db = SessionLocal()
    config = db.query(ClusterConfig).filter_by(name=name).first()
    if not config or not config.network:
        return HTMLResponse("")

    render_metallb_yaml(config.name, config.network)
    return HTMLResponse("")  # Button löst nur Stream aus

@router.get("/streammetallb")
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
                    decoded = line.decode().rstrip()
                    print(f"[DEBUG] Output: {decoded}")
                    yield f"data: {decoded}\n\n"
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

@router.post("/install-istio")
def install_istio(name: str = Form(...)):
    return HTMLResponse("")  # Stream übernimmt die Aktion

@router.get("/streamistio")
async def stream_istio(request: Request, name: str):
    from config import (
        ISTIO_SYSTEM_NAMESPACE,
        MESH_ID,
        MESH_NETWORK,
        ISTIO_VERSION
    )

    async def event_generator():
        yield f"data: Installing Istio {ISTIO_VERSION} on {name}\n\n"

        commands = [
            ["helm", "repo", "add", "istio", "https://istio-release.storage.googleapis.com/charts"],
            ["helm", "repo", "update"],
            ["bash", "-c", f"kubectl --context kind-{name} get namespace {ISTIO_SYSTEM_NAMESPACE} --ignore-not-found || kubectl --context kind-{name} create namespace {ISTIO_SYSTEM_NAMESPACE}"],
            ["helm", "install", "istio-base", "istio/base",
             "-n", ISTIO_SYSTEM_NAMESPACE,
             "--kube-context", f"kind-{name}",
             "--version", ISTIO_VERSION,
             "--wait"],
            ["helm", "install", "istiod", "istio/istiod",
             "-n", ISTIO_SYSTEM_NAMESPACE,
             "--kube-context", f"kind-{name}",
             "--version", ISTIO_VERSION,
             "--set", f"global.meshID={MESH_ID}",
             "--set", f"global.multiCluster.clusterName={name}",
             "--set", f"global.network={MESH_NETWORK}",
             "--wait"],
            ["helm", "install", "istio-ingressgateway", "istio/gateway",
             "-n", ISTIO_SYSTEM_NAMESPACE,
             "--kube-context", f"kind-{name}",
             "--version", ISTIO_VERSION,
             "--wait"]
        ]

        success = True
        for cmd in commands:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT
            )
            async for line in proc.stdout:
                decoded = line.decode().rstrip()
                print(f"[DEBUG] Output: {decoded}")
                yield f"data: {decoded}\n\n"
            returncode = await proc.wait()
            if returncode != 0:
                success = False
                yield f"data: Command failed: {' '.join(cmd)}\n\n"
                break

        if success:
            db = SessionLocal()
            config = db.query(ClusterConfig).filter_by(name=name).first()
            if config:
                config.istioinstalled = True
                db.commit()
            yield "data: Istio installation complete.\n\n"
        else:
            yield "data: Istio installation aborted due to error.\n\n"

        yield "data: [STREAM CLOSED]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
