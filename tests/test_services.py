"""Job requests through Claude (real SDK, canned responses), the rules, the console and the CLI."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import anthropic
import httpx2
import pytest
from fastapi.testclient import TestClient

from fieldops.app import SAMPLE, Console, create_app, demo_console
from fieldops.cli import main
from fieldops.intake import FALLBACK_BETA, MODEL, Reader, rules


def message(*content: dict[str, Any], stop: str = "tool_use") -> dict[str, Any]:
    return {
        "id": "m",
        "type": "message",
        "role": "assistant",
        "model": MODEL,
        "content": list(content),
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


class Script:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self.responses: Iterator[dict[str, Any]] = iter(responses)
        self.requests: list[dict[str, Any]] = []
        self.headers: list[httpx2.Headers] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        self.headers.append(request.headers)
        return httpx2.Response(200, json=next(self.responses))


def reader(script: Script) -> Reader:
    client = anthropic.Anthropic(
        api_key="test",
        base_url="http://api.test",
        max_retries=0,
        http_client=httpx2.Client(transport=httpx2.MockTransport(script)),
    )
    return Reader(client)


def call(**fields: Any) -> dict[str, Any]:
    base = {
        "skill": "appliance",
        "fault": "dishwasher not draining",
        "brand": "Elkin",
        "window": "morning",
        "fault_quote": "leaves water at the bottom",
    }
    base.update(fields)
    return {"type": "tool_use", "id": "t", "name": "record_job", "input": base}


def test_request_shape_and_a_clean_read() -> None:
    script = Script([message(call())])
    r = reader(script).read(SAMPLE)
    assert (r.skill, r.fault, r.brand, r.window, r.source) == (
        "appliance",
        "dishwasher not draining",
        "Elkin",
        "morning",
        "claude",
    )
    req = script.requests[0]
    assert req["model"] == MODEL and req["output_config"] == {"effort": "low"} and req["fallbacks"] == "default"
    assert "thinking" not in req and "tool_choice" not in req and req["tools"][0]["strict"] is True
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"} and "<request>" in req["messages"][0]["content"]
    assert FALLBACK_BETA in script.headers[0]["anthropic-beta"]


def test_answers_that_dont_check_out() -> None:
    r = reader(Script([message(call(skill="hvac"))])).read(SAMPLE)  # fault not in that skill
    assert r.fault == "dishwasher not draining" and "rules" in r.notes[0]
    r = reader(Script([message(call(fault_quote="the oven is cold", brand="Brisk"))])).read(SAMPLE)
    assert r.skill == "appliance" and r.brand is None and any("not in the message" in n for n in r.notes)
    r = reader(Script([message(call(brand="Garro"))])).read("Our Garro dishwasher leaves water at the bottom")
    assert r.brand == "Garro" and not r.known_brand and any("no history" in n for n in r.notes)


def test_refusal_falls_back_to_rules() -> None:
    r = reader(Script([message({"type": "text", "text": "no"}, stop="refusal")])).read(SAMPLE)
    assert r.source == "rules" and r.fault == "dishwasher not draining" and "Claude gave no answer" in r.notes[-1]
    assert rules("The breaker trips every evening, any time after lunch").fault == "tripping breaker"
    assert rules("The breaker trips every evening, any time after lunch").window == "afternoon"


@pytest.fixture(scope="module")
def console() -> Console:
    return demo_console()


@pytest.fixture(scope="module")
def client(console: Console) -> TestClient:
    return TestClient(create_app(console))


def test_console_pages(client: TestClient, console: Console) -> None:
    assert client.get("/healthz").json()["jobs"] == len(console.jobs)
    home = client.get("/").text
    assert "<svg" in home and "Parts added for the day" in home
    tid = next(t for t, r in console.plan.routes.items() if r)
    page = client.get(f"/techs/{tid}").text
    assert "Chance the van" in page and "Arrive" in page
    assert client.get("/techs/99").status_code == 404
    assert "Parts this job is likely to need" in client.get("/intake").text


def test_console_api(client: TestClient, console: Console) -> None:
    plan = client.get("/api/plan").json()
    assert len(plan) == len(console.region.techs) and {"km", "stops", "back"} <= set(plan[0])
    r = client.post("/api/jobs", json={"text": SAMPLE}).json()
    assert r["fault"] == "dishwasher not draining" and r["window"] == "morning"
    assert client.post("/api/jobs", json={"text": " "}).status_code == 422
    assert client.post("/intake", data={"text": ""}).status_code == 422
    assert "dishwasher" in client.post("/intake", data={"text": SAMPLE}).text


def test_cli(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["plan"]) == 0
    assert "km" in capsys.readouterr().out
    assert main(["read", "The fridge is warm"]) == 0
    assert json.loads(capsys.readouterr().out)["fault"] == "fridge not cooling"
