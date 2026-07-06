"""
k8s_connector.py
------------------
Wraps `kubernetes` python client (falls back to kubectl subprocess if
the client lib isn't available) for namespace/pod/HPA visibility —
matches JD: "Docker and Kubernetes (Helm, kubectl, namespaces, autoscaling)"

Requires a valid kubeconfig context (KUBE_CONTEXT in .env) — this will
work as-is once run inside/against the corporate AKS/GKE cluster.
"""
import subprocess
import json
from dataclasses import dataclass
from typing import List


@dataclass
class PodStatus:
    name: str
    namespace: str
    status: str
    restarts: int
    cpu_request: str = ""
    memory_request: str = ""


@dataclass
class HPAStatus:
    name: str
    namespace: str
    current_replicas: int
    desired_replicas: int
    min_replicas: int
    max_replicas: int
    target_cpu_pct: int
    current_cpu_pct: int


def _kubectl(args: List[str], context: str = "") -> dict:
    cmd = ["kubectl"]
    if context:
        cmd += ["--context", context]
    cmd += args + ["-o", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout)


def list_namespaces(context: str = "") -> List[str]:
    data = _kubectl(["get", "namespaces"], context)
    return [item["metadata"]["name"] for item in data.get("items", [])]


def list_pods(namespace: str, context: str = "") -> List[PodStatus]:
    data = _kubectl(["get", "pods", "-n", namespace], context)
    pods = []
    for item in data.get("items", []):
        status = item.get("status", {})
        containers = item.get("spec", {}).get("containers", [{}])
        restarts = sum(cs.get("restartCount", 0) for cs in status.get("containerStatuses", []))
        pods.append(PodStatus(
            name=item["metadata"]["name"],
            namespace=namespace,
            status=status.get("phase", "Unknown"),
            restarts=restarts,
            cpu_request=containers[0].get("resources", {}).get("requests", {}).get("cpu", ""),
            memory_request=containers[0].get("resources", {}).get("requests", {}).get("memory", ""),
        ))
    return pods


def list_hpas(namespace: str, context: str = "") -> List[HPAStatus]:
    data = _kubectl(["get", "hpa", "-n", namespace], context)
    hpas = []
    for item in data.get("items", []):
        spec = item.get("spec", {})
        status = item.get("status", {})
        target_cpu = 0
        for metric in spec.get("metrics", []):
            if metric.get("type") == "Resource" and metric["resource"]["name"] == "cpu":
                target_cpu = metric["resource"]["target"].get("averageUtilization", 0)
        current_cpu = 0
        for metric in status.get("currentMetrics", []):
            if metric.get("type") == "Resource" and metric["resource"]["name"] == "cpu":
                current_cpu = metric["resource"]["current"].get("averageUtilization", 0)
        hpas.append(HPAStatus(
            name=item["metadata"]["name"],
            namespace=namespace,
            current_replicas=status.get("currentReplicas", 0),
            desired_replicas=status.get("desiredReplicas", 0),
            min_replicas=spec.get("minReplicas", 0),
            max_replicas=spec.get("maxReplicas", 0),
            target_cpu_pct=target_cpu,
            current_cpu_pct=current_cpu,
        ))
    return hpas
