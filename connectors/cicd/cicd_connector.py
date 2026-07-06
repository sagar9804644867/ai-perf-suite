"""
cicd_connector.py
-------------------
Pull recent pipeline/build status from Jenkins, GitHub Actions, or
GitLab CI — so performance test gates (e.g. "fail build if P95 > 500ms")
show up alongside the rest of the perf suite.
"""
import requests
from dataclasses import dataclass
from typing import List


@dataclass
class BuildStatus:
    source: str        # jenkins / github / gitlab
    pipeline_name: str
    build_number: str
    status: str        # SUCCESS / FAILURE / RUNNING
    duration_sec: float
    url: str = ""


def get_jenkins_builds(base_url: str, job_name: str, user: str, api_token: str, limit: int = 5) -> List[BuildStatus]:
    r = requests.get(
        f"{base_url}/job/{job_name}/api/json",
        params={"tree": f"builds[number,result,duration,url]{{0,{limit}}}"},
        auth=(user, api_token), timeout=15,
    )
    r.raise_for_status()
    builds = []
    for b in r.json().get("builds", []):
        builds.append(BuildStatus(
            source="jenkins", pipeline_name=job_name,
            build_number=str(b.get("number")),
            status=b.get("result") or "RUNNING",
            duration_sec=(b.get("duration", 0) or 0) / 1000,
            url=b.get("url", ""),
        ))
    return builds


def get_github_actions_runs(owner: str, repo: str, token: str, limit: int = 5) -> List[BuildStatus]:
    r = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/actions/runs",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        params={"per_page": limit}, timeout=15,
    )
    r.raise_for_status()
    runs = []
    for run in r.json().get("workflow_runs", []):
        runs.append(BuildStatus(
            source="github", pipeline_name=run.get("name", ""),
            build_number=str(run.get("run_number")),
            status=(run.get("conclusion") or run.get("status", "")).upper(),
            duration_sec=0,  # requires timing calc from created_at/updated_at if needed
            url=run.get("html_url", ""),
        ))
    return runs


def get_gitlab_pipelines(base_url: str, project_id: str, token: str, limit: int = 5) -> List[BuildStatus]:
    r = requests.get(
        f"{base_url}/api/v4/projects/{project_id}/pipelines",
        headers={"PRIVATE-TOKEN": token},
        params={"per_page": limit}, timeout=15,
    )
    r.raise_for_status()
    pipelines = []
    for p in r.json():
        pipelines.append(BuildStatus(
            source="gitlab", pipeline_name=f"pipeline-{p.get('id')}",
            build_number=str(p.get("id")),
            status=p.get("status", "").upper(),
            duration_sec=0,
            url=p.get("web_url", ""),
        ))
    return pipelines
