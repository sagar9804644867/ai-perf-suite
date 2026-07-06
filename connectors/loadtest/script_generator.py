"""
script_generator.py
--------------------
Takes a recorded HAR file (exported from Chrome DevTools Network tab,
Playwright trace-to-HAR, or any browser recording) and generates
ready-to-run load test scripts for JMeter, Gatling, Locust, and k6.

Recording sources supported:
  - Chrome/Edge DevTools -> "Save all as HAR with content"
  - Playwright: context.tracing / page.route -> har export
  - Any HAR 1.2 compliant capture

Usage (from Streamlit page or CLI):
    entries = parse_har("recording.har")
    entries = filter_entries(entries, include_domains=["yourapp.com"], exclude_ext=[".png",".css",".js"])
    jmx  = generate_jmeter_jmx(entries, thread_count=50, ramp_up=30, loops=1, test_name="Checkout_Flow")
    scala = generate_gatling_scala(entries, sim_name="CheckoutSimulation")
    py    = generate_locust_py(entries, class_name="CheckoutUser")
    js    = generate_k6_js(entries, vus=50, duration="1m")
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse, parse_qsl
from xml.sax.saxutils import escape as xml_escape


# --------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------

@dataclass
class RecordedRequest:
    method: str
    url: str
    path: str
    domain: str
    headers: dict
    query_params: list
    post_data: Optional[str]
    mime_type: Optional[str]
    status: int
    time_ms: float
    resource_type: str = "other"  # xhr, document, script, stylesheet, image, font, other


# --------------------------------------------------------------------------
# HAR parsing
# --------------------------------------------------------------------------

DEFAULT_EXCLUDED_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2",
                         ".ttf", ".ico", ".css", ".map")

# Headers that are noisy/browser-specific and should not be replayed verbatim
NOISY_HEADERS = {
    "cookie", "content-length", ":authority", ":method", ":path", ":scheme",
    "accept-encoding", "sec-ch-ua", "sec-ch-ua-mobile", "sec-ch-ua-platform",
    "sec-fetch-dest", "sec-fetch-mode", "sec-fetch-site", "sec-fetch-user",
    "upgrade-insecure-requests",
}


def parse_har(har_path: str) -> List[RecordedRequest]:
    """Parse a HAR file into a list of RecordedRequest objects."""
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)

    entries = har.get("log", {}).get("entries", [])
    parsed: List[RecordedRequest] = []

    for entry in entries:
        req = entry.get("request", {})
        res = entry.get("response", {})
        url = req.get("url", "")
        parsed_url = urlparse(url)

        headers = {h["name"]: h["value"] for h in req.get("headers", [])
                   if h["name"].lower() not in NOISY_HEADERS}

        post_data = None
        if "postData" in req:
            post_data = req["postData"].get("text")

        mime_type = res.get("content", {}).get("mimeType", "")
        resource_type = _classify_resource(parsed_url.path, mime_type)

        parsed.append(RecordedRequest(
            method=req.get("method", "GET"),
            url=url,
            path=parsed_url.path or "/",
            domain=parsed_url.netloc,
            headers=headers,
            query_params=parse_qsl(parsed_url.query),
            post_data=post_data,
            mime_type=mime_type,
            status=res.get("status", 0),
            time_ms=entry.get("time", 0),
            resource_type=resource_type,
        ))

    return parsed


def _classify_resource(path: str, mime_type: str) -> str:
    path_lower = path.lower()
    if any(path_lower.endswith(ext) for ext in DEFAULT_EXCLUDED_EXT):
        return "static"
    if "json" in mime_type or "xhr" in mime_type:
        return "xhr"
    if "html" in mime_type:
        return "document"
    return "other"


def filter_entries(
    entries: List[RecordedRequest],
    include_domains: Optional[List[str]] = None,
    exclude_ext: Optional[List[str]] = None,
    xhr_only: bool = False,
) -> List[RecordedRequest]:
    """Narrow down a HAR capture to the business-relevant calls before
    generating scripts (drops static assets, third-party trackers, etc.)."""
    exclude_ext = exclude_ext or list(DEFAULT_EXCLUDED_EXT)
    out = []
    for e in entries:
        if any(e.path.lower().endswith(ext) for ext in exclude_ext):
            continue
        if include_domains and not any(d in e.domain for d in include_domains):
            continue
        if xhr_only and e.resource_type != "xhr":
            continue
        out.append(e)
    return out


# --------------------------------------------------------------------------
# JMeter (.jmx) generation
# --------------------------------------------------------------------------

def generate_jmeter_jmx(
    entries: List[RecordedRequest],
    thread_count: int = 50,
    ramp_up: int = 30,
    loops: int = 1,
    test_name: str = "Recorded_Test_Plan",
) -> str:
    samplers = []
    for e in entries:
        parsed = urlparse(e.url)
        query_str = ""
        arg_elements = ""
        if e.query_params:
            for k, v in e.query_params:
                arg_elements += f"""
              <elementProp name="{xml_escape(k)}" elementType="HTTPArgument">
                <boolProp name="HTTPArgument.always_encode">true</boolProp>
                <stringProp name="Argument.value">{xml_escape(str(v))}</stringProp>
                <stringProp name="Argument.name">{xml_escape(k)}</stringProp>
              </elementProp>"""

        body_prop = ""
        if e.post_data:
            body_prop = f"""
        <boolProp name="HTTPSampler.postBodyRaw">true</boolProp>
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
          <collectionProp name="Arguments.arguments">
            <elementProp name="" elementType="HTTPArgument">
              <stringProp name="Argument.value">{xml_escape(e.post_data)}</stringProp>
              <stringProp name="Argument.metadata">=</stringProp>
            </elementProp>
          </collectionProp>
        </elementProp>"""

        samplers.append(f"""
      <HTTPSamplerProxy guiclass="HttpTestSampleGui" testclass="HTTPSamplerProxy" testname="{xml_escape(e.method)} {xml_escape(e.path)}">
        <stringProp name="HTTPSampler.domain">{xml_escape(parsed.hostname or "")}</stringProp>
        <stringProp name="HTTPSampler.port">{parsed.port or (443 if parsed.scheme == "https" else 80)}</stringProp>
        <stringProp name="HTTPSampler.protocol">{parsed.scheme}</stringProp>
        <stringProp name="HTTPSampler.path">{xml_escape(parsed.path)}</stringProp>
        <stringProp name="HTTPSampler.method">{xml_escape(e.method)}</stringProp>
        <boolProp name="HTTPSampler.follow_redirects">true</boolProp>
        <boolProp name="HTTPSampler.use_keepalive">true</boolProp>{body_prop}
        <elementProp name="HTTPsampler.Arguments" elementType="Arguments">
          <collectionProp name="Arguments.arguments">{arg_elements}
          </collectionProp>
        </elementProp>
      </HTTPSamplerProxy>
      <hashTree/>""")

    samplers_xml = "\n".join(samplers)

    jmx = f"""<?xml version="1.0" encoding="UTF-8"?>
<jmeterTestPlan version="1.2" properties="5.0" jmeter="5.6">
  <hashTree>
    <TestPlan guiclass="TestPlanGui" testclass="TestPlan" testname="{xml_escape(test_name)}">
      <boolProp name="TestPlan.functional_mode">false</boolProp>
      <stringProp name="TestPlan.user_define_classpath"></stringProp>
    </TestPlan>
    <hashTree>
      <ThreadGroup guiclass="ThreadGroupGui" testclass="ThreadGroup" testname="Recorded Thread Group">
        <stringProp name="ThreadGroup.num_threads">{thread_count}</stringProp>
        <stringProp name="ThreadGroup.ramp_time">{ramp_up}</stringProp>
        <elementProp name="ThreadGroup.main_controller" elementType="LoopController">
          <stringProp name="LoopController.loops">{loops}</stringProp>
          <boolProp name="LoopController.continue_forever">false</boolProp>
        </elementProp>
      </ThreadGroup>
      <hashTree>{samplers_xml}
        <ResultCollector guiclass="ViewResultsFullVisualizer" testclass="ResultCollector" testname="View Results Tree">
          <stringProp name="filename"></stringProp>
        </ResultCollector>
        <hashTree/>
      </hashTree>
    </hashTree>
  </hashTree>
</jmeterTestPlan>
"""
    return jmx


# --------------------------------------------------------------------------
# Gatling (Scala DSL) generation
# --------------------------------------------------------------------------

def generate_gatling_scala(
    entries: List[RecordedRequest],
    sim_name: str = "RecordedSimulation",
    users: int = 50,
    ramp_seconds: int = 30,
) -> str:
    steps = []
    for i, e in enumerate(entries):
        name = f'"{e.method} {e.path}"'
        body_line = ""
        if e.post_data:
            escaped = e.post_data.replace('"', '\\"')
            body_line = f'\n      .body(StringBody("""{escaped}"""))'
        headers_map = ", ".join(f'"{k}" -> "{v}"' for k, v in list(e.headers.items())[:6])
        header_line = f"\n      .headers(Map({headers_map}))" if headers_map else ""

        steps.append(f"""
    exec(
      http({name})
        .{e.method.lower()}("{e.path}"){header_line}{body_line}
    )
    .pause(1)""")

    steps_scala = "".join(steps)

    scala = f"""import io.gatling.core.Predef._
import io.gatling.http.Predef._
import scala.concurrent.duration._

class {sim_name} extends Simulation {{

  val httpProtocol = http
    .baseUrl("https://{entries[0].domain if entries else 'CHANGE_ME.example.com'}")
    .acceptHeader("application/json, text/plain, */*")
    .userAgentHeader("Gatling/AI-Perf-Suite")

  val scn = scenario("RecordedScenario"){steps_scala}

  setUp(
    scn.inject(rampUsers({users}).during({ramp_seconds}.seconds))
  ).protocols(httpProtocol)
}}
"""
    return scala


# --------------------------------------------------------------------------
# Locust (Python) generation
# --------------------------------------------------------------------------

def generate_locust_py(
    entries: List[RecordedRequest],
    class_name: str = "RecordedUser",
    wait_min: float = 1.0,
    wait_max: float = 3.0,
) -> str:
    tasks = []
    for i, e in enumerate(entries):
        method = e.method.lower()
        kwargs = ""
        if e.post_data:
            escaped = e.post_data.replace('"""', "'''")
            kwargs = f', data="""{escaped}"""'
        if e.headers:
            hdrs = json.dumps({k: v for k, v in list(e.headers.items())[:6]})
            kwargs += f", headers={hdrs}"

        tasks.append(f"""
    @task
    def step_{i}_{re.sub(r'[^a-zA-Z0-9_]', '_', e.path)[:30] or 'root'}(self):
        self.client.{method}("{e.path}"{kwargs}, name="{e.method} {e.path}")""")

    tasks_py = "".join(tasks)

    py = f'''"""
Auto-generated Locust script from HAR recording.
Run with: locust -f this_file.py --host https://{entries[0].domain if entries else 'CHANGE_ME.example.com'}
"""
from locust import HttpUser, task, between


class {class_name}(HttpUser):
    wait_time = between({wait_min}, {wait_max}){tasks_py}
'''
    return py


# --------------------------------------------------------------------------
# k6 (JavaScript) generation
# --------------------------------------------------------------------------

def generate_k6_js(
    entries: List[RecordedRequest],
    vus: int = 50,
    duration: str = "1m",
) -> str:
    lines = []
    for e in entries:
        headers_js = json.dumps({k: v for k, v in list(e.headers.items())[:6]})
        if e.method.upper() == "GET":
            lines.append(f'  res = http.get(`{e.url}`, {{ headers: {headers_js} }});')
        else:
            body = json.dumps(e.post_data) if e.post_data else '""'
            lines.append(
                f'  res = http.{e.method.lower()}(`{e.url}`, {body}, {{ headers: {headers_js} }});'
            )
        lines.append(f'  check(res, {{ "{e.method} {e.path} status ok": (r) => r.status < 400 }});')
        lines.append("  sleep(1);\n")

    body_js = "\n".join(lines)

    js = f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {{
  vus: {vus},
  duration: '{duration}',
  thresholds: {{
    http_req_duration: ['p(95)<1000', 'p(99)<2000'],
    http_req_failed: ['rate<0.01'],
  }},
}};

export default function () {{
  let res;
{body_js}
}}
"""
    return js
