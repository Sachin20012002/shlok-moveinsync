import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import asdict, dataclass

import httpx
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.database.models import DatasetUpload, Incident, MetricSnapshot, Trip
from app.schemas.api import MobilityAgentRequest
from app.services.agent_tools import AGENT_TOOLS, execute_agent_tool


@dataclass
class AgentContext:
    scope: str
    source_file: str | None
    completed_trips: int
    delayed_trips: int
    affected_employees: int
    ota: float | None
    ota_sla: float
    attention_incidents: int
    top_incidents: list[dict[str, object]]
    selected_incident: dict[str, object] | None


def _known_value(value: str | None) -> str | None:
    if value is None or value.strip().lower() in {"", "unavailable", "unknown", "n/a", "na"}:
        return None
    return value


def build_agent_context(
    session: Session,
    settings: Settings,
    incident_id: int | None = None,
) -> AgentContext:
    upload = session.scalar(select(DatasetUpload).order_by(desc(DatasetUpload.id)).limit(1))
    snapshot = session.scalar(select(MetricSnapshot).order_by(desc(MetricSnapshot.id)).limit(1))
    incidents = list(
        session.scalars(
            select(Incident)
            .where(Incident.attention_required.is_(True))
            .order_by(desc(Incident.updated_at))
            .limit(8)
        )
    )
    attention_incidents = session.scalar(
        select(func.count()).select_from(Incident).where(Incident.attention_required.is_(True))
    ) or 0
    completed_trips = snapshot.completed_trips if snapshot else session.scalar(
        select(func.count()).select_from(Trip).where(Trip.status == "completed")
    ) or 0
    selected = session.get(Incident, incident_id) if incident_id is not None else None
    if incident_id is not None and selected is None:
        raise LookupError("Incident not found")
    return AgentContext(
        scope="incident" if selected else "general",
        source_file=upload.filename if upload else None,
        completed_trips=completed_trips,
        delayed_trips=snapshot.delayed_trips if snapshot else 0,
        affected_employees=snapshot.affected_employees if snapshot else 0,
        ota=snapshot.ota_value if snapshot else None,
        ota_sla=snapshot.sla_value if snapshot else settings.ota_sla,
        attention_incidents=attention_incidents,
        top_incidents=[] if selected else [
            {
                "id": incident.id,
                "title": incident.title,
                "severity": incident.severity,
                "status": incident.status,
                "value": incident.current_value,
                "sla": incident.sla_value,
                "reason": incident.reason,
                "recommended_action": incident.recommended_action,
            }
            for incident in incidents
        ],
        selected_incident=(
            {
                "id": selected.id,
                "title": selected.title,
                "severity": selected.severity,
                "status": selected.status,
                "value": selected.current_value,
                "sla": selected.sla_value,
                "affected_employees": selected.affected_employees,
                "vendor": _known_value(selected.contributing_vendor),
                "route": _known_value(selected.contributing_route),
                "shift": _known_value(selected.contributing_shift),
                "reason": selected.reason,
                "recommended_action": selected.recommended_action,
                "notification_count": selected.notification_count,
            }
            if selected else None
        ),
    )


def _local_answer(message: str, context: AgentContext) -> str:
    if context.selected_incident:
        incident = context.selected_incident
        return (
            f"Incident analysis: {incident['title']}\n\n"
            f"Current facts\n"
            f"- Performance is {incident['value']}% against a {incident['sla']}% SLA.\n"
            f"- Severity is {incident['severity']} and status is {incident['status']}.\n"
            f"- {incident['affected_employees']:,} employees are affected.\n"
            f"- Evidence: {incident['reason']}\n\n"
            f"Recommended response\n- {incident['recommended_action']}\n"
            f"- Notification count: {incident['notification_count']}.\n\n"
            "This answer is scoped only to the selected incident and is advisory; no incident state was changed."
        )
    ota = "unavailable" if context.ota is None else f"{context.ota:.2f}%"
    incident_lines = "\n".join(
        f"- {item['title']}: {item['value']}% vs {item['sla']}% SLA ({item['severity']}). Action: {item['recommended_action']}"
        for item in context.top_incidents[:4]
    ) or "- No incidents currently require attention."
    question = message.lower()
    if any(word in question for word in ("priority", "focus", "action", "do next")):
        opening = "Prioritize the largest active SLA gaps and assign owners before the next shift."
    elif any(word in question for word in ("summary", "status", "health", "today")):
        opening = "The current operation is below its OTA target and requires active recovery management."
    elif any(word in question for word in ("vendor", "supplier")):
        opening = "Vendor-level incidents show where recovery conversations should start."
    else:
        opening = "I reviewed your question against the current mobility snapshot."
    return (
        f"{opening}\n\n"
        f"Current facts\n"
        f"- OTA is {ota} against a {context.ota_sla:.0f}% SLA.\n"
        f"- {context.delayed_trips:,} of {context.completed_trips:,} completed trips are delayed.\n"
        f"- {context.affected_employees:,} employees are affected.\n"
        f"- {context.attention_incidents} incidents need attention.\n\n"
        f"Highest-priority signals\n{incident_lines}\n\n"
        "This response is grounded in the current dashboard snapshot. Confirm operational actions with the assigned manager."
    )


def _event(name: str, payload: dict[str, object]) -> str:
    return f"event: {name}\ndata: {json.dumps(payload)}\n\n"


def _model_context(context: AgentContext) -> dict[str, object]:
    if context.selected_incident:
        return {"scope": "incident", "selected_incident": context.selected_incident}
    return asdict(context)


async def _stream_openai(
    request: MobilityAgentRequest,
    context: AgentContext,
    settings: Settings,
) -> AsyncIterator[str]:
    system_prompt = (
        "You are SHLOK Mobility Agent, an enterprise transport operations analyst. "
        "Use only the supplied operational context. Separate facts from recommendations, "
        "never invent routes, vendors, causes, or live conditions, and keep answers concise. "
        "A null field means metadata was not provided; do not describe it as unavailable, "
        "offline, disrupted, or requiring restoration. Do not phrase a question with a factual "
        "premise unless that fact appears in the context. When scope is incident, discuss only "
        "the selected incident unless the user explicitly asks for a broader comparison. Preserve "
        "all supplied counts and rates verbatim; never derive, recalculate, or substitute them.\n\n"
        f"OPERATIONAL CONTEXT:\n{json.dumps(_model_context(context), default=str)}"
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(
        {"role": item.role, "content": item.content}
        for item in request.history[-10:]
        if item.role in {"user", "assistant"}
    )
    messages.append({"role": "user", "content": request.message})
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{settings.ai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_api_key}"},
            json={"model": settings.ai_model, "messages": messages, "stream": True},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                payload = json.loads(line[6:])
                content = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                if content:
                    yield content


async def _stream_sarvam(
    request: MobilityAgentRequest,
    context: AgentContext,
    settings: Settings,
    session: Session,
) -> AsyncIterator[str]:
    system_prompt = (
        "You are SHLOK Mobility Agent, an enterprise transport operations analyst. "
        "Use only the supplied operational context. Separate facts from recommendations, "
        "never invent routes, vendors, causes, or live conditions, and keep answers concise. "
        "A null field means metadata was not provided; do not describe it as unavailable, "
        "offline, disrupted, or requiring restoration. Do not phrase a question with a factual "
        "premise unless that fact appears in the context. When scope is incident, discuss only "
        "the selected incident unless the user explicitly asks for a broader comparison. Preserve "
        "all supplied counts and rates verbatim; never derive, recalculate, or substitute them. "
        "For every question whose answer depends on trip, delay, vendor, office, shift, safety, "
        "employee, no-show, feedback, or trend records, call the most specific available tool before "
        "answering. Use the function descriptions to select the tool. If a tool allows omitted dates, "
        "omit them to search the complete loaded dataset. Never claim there is insufficient data "
        "before calling the relevant tool. Treat tool results as authoritative, preserve their values "
        "verbatim, and clearly state when a result says data is unavailable.\n\n"
        f"OPERATIONAL CONTEXT:\n{json.dumps(_model_context(context), default=str)}"
    )
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(
        {"role": item.role, "content": item.content}
        for item in request.history[-10:]
        if item.role in {"user", "assistant"}
    )
    messages.append({"role": "user", "content": request.message})
    async with httpx.AsyncClient(timeout=60) as client:
        url = f"{settings.ai_base_url.rstrip('/')}/v1/chat/completions"
        headers = {"api-subscription-key": settings.ai_api_key or ""}
        for _ in range(3):
            response = await client.post(
                url,
                headers=headers,
                json={
                    "model": settings.ai_model,
                    "messages": messages,
                    "tools": AGENT_TOOLS,
                    "tool_choice": "auto",
                    "reasoning_effort": None,
                },
            )
            response.raise_for_status()
            message = response.json()["choices"][0]["message"]
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                if content := message.get("content"):
                    yield content
                    return
                raise ValueError("Sarvam returned no answer")

            messages.append(message)
            for tool_call in tool_calls:
                result = execute_agent_tool(
                    session,
                    settings,
                    tool_call["function"]["name"],
                    tool_call["function"]["arguments"],
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result),
                })
        raise ValueError("Sarvam exceeded the tool-call limit")


async def stream_agent_response(
    request: MobilityAgentRequest,
    context: AgentContext,
    settings: Settings,
    session: Session,
) -> AsyncIterator[str]:
    provider = settings.ai_provider.lower()
    mode = "model" if settings.ai_api_key else "grounded-local"
    yield _event(
        "context",
        {
            "mode": mode,
            "model": settings.ai_model if settings.ai_api_key else None,
            "sourceFile": context.source_file,
            "completedTrips": context.completed_trips,
            "attentionIncidents": context.attention_incidents,
            "scope": context.scope,
            "incidentId": context.selected_incident["id"] if context.selected_incident else None,
            "incidentTitle": context.selected_incident["title"] if context.selected_incident else None,
        },
    )
    try:
        if settings.ai_api_key and provider == "sarvam":
            async for token in _stream_sarvam(request, context, settings, session):
                yield _event("token", {"content": token})
        elif settings.ai_api_key:
            async for token in _stream_openai(request, context, settings):
                yield _event("token", {"content": token})
        else:
            for token in _local_answer(request.message, context).split(" "):
                yield _event("token", {"content": f"{token} "})
                await asyncio.sleep(0.01)
        yield _event("done", {"ok": True})
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as error:
        yield _event("error", {"message": f"Agent provider error: {type(error).__name__}"})
        yield _event("done", {"ok": False})
