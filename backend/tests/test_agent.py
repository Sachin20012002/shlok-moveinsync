import asyncio
import json
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database.connection import Base, get_db
from app.database.models import DatasetUpload, Incident, SafetyAlert, Trip, TripFeedback
from app.main import app, settings
from app.schemas.api import MobilityAgentRequest
from app.services.agent import AgentContext, _model_context, _stream_sarvam, build_agent_context
from app.services.agent_tools import AGENT_TOOLS, execute_agent_tool
from app.services.detection import evaluate_operations
from app.core.config import Settings


def test_agent_streams_grounded_sse_without_mutating_incidents(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ai_api_key", None)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 9, 5, 9, 0)

    with Session(engine) as session:
        upload = DatasetUpload(filename="agent-test.csv", valid_rows=10, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all(
            [
                Trip(
                    dataset_upload_id=upload.id,
                    trip_id=f"AGENT-{index}",
                    vendor_id="Vendor A",
                    route_id="Route 1",
                    shift_id="Morning",
                    employee_id=f"EMP-{index}",
                    transport_mode="CAB",
                    scheduled_arrival=scheduled,
                    actual_arrival=scheduled + timedelta(minutes=12 if index < 3 else 2),
                    status="completed",
                    gps_available=True,
                )
                for index in range(10)
            ]
        )
        session.commit()
        evaluate_operations(session, upload.id, Settings(database_url="sqlite://"))
        incident = session.scalar(select(Incident))
        assert incident is not None
        incident.contributing_route = "Unavailable"
        session.commit()
        context = build_agent_context(session, Settings(database_url="sqlite://"), incident.id)
        assert context.selected_incident is not None
        assert context.selected_incident["route"] is None
        assert context.top_incidents == []
        assert _model_context(context) == {
            "scope": "incident",
            "selected_incident": context.selected_incident,
        }

    def test_database():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_database
    try:
        with TestClient(app) as client:
            before = client.get("/api/incidents").json()
            trip_summary = client.get(
                "/api/tools/trips/summary",
                params={"startDate": "2026-09-05", "endDate": "2026-09-05"},
            )
            response = client.post(
                "/api/agent/chat",
                json={"message": "Summarize current health", "history": []},
            )
            after = client.get("/api/incidents").json()

        assert response.status_code == 200
        assert trip_summary.status_code == 200
        assert trip_summary.json()["totalTrips"] == 10
        assert trip_summary.json()["delayedTrips"] == 3
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.startswith("event: context\n")
        assert "event: token\n" in response.text
        assert "70.00%" in response.text
        assert response.text.rstrip().endswith('data: {"ok": true}')
        assert before == after

        incident_id = before[0]["id"]
        with TestClient(app) as client:
            scoped = client.post(
                "/api/agent/chat",
                json={
                    "message": "Explain this incident",
                    "history": [],
                    "incidentId": incident_id,
                },
            )
            missing = client.post(
                "/api/agent/chat",
                json={"message": "Explain this incident", "incidentId": 99999},
            )

        assert scoped.status_code == 200
        assert '"scope": "incident"' in scoped.text
        assert f'"incidentId": {incident_id}' in scoped.text
        scoped_answer = "".join(
            json.loads(line[6:])["content"]
            for line in scoped.text.splitlines()
            if line.startswith("data: ") and '"content"' in line
        )
        assert "Incident analysis:" in scoped_answer
        assert missing.status_code == 404
        assert missing.json()["detail"] == "Incident not found"

    finally:
        app.dependency_overrides.clear()


def test_sarvam_executes_trip_summary_tool_and_returns_grounded_answer(monkeypatch) -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    scheduled = datetime(2026, 7, 1, 9, 0)
    with Session(engine) as session:
        upload = DatasetUpload(filename="july.csv", valid_rows=1, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add(Trip(
            dataset_upload_id=upload.id,
            trip_id="JULY-1",
            vendor_id="Vendor A",
            route_id="Route 1",
            shift_id="Morning",
            employee_id="EMP-1",
            transport_mode="CAB",
            scheduled_arrival=scheduled,
            actual_arrival=scheduled + timedelta(minutes=2),
            status="completed",
            gps_available=True,
        ))
        session.commit()

        requests: list[dict[str, object]] = []

        class MockResponse:
            def __init__(self, payload: dict[str, object]) -> None:
                self.payload = payload

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return self.payload

        class MockAsyncClient:
            def __init__(self, **_kwargs: object) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

            async def post(self, _url: str, **kwargs: object) -> MockResponse:
                request_json = kwargs["json"]
                assert isinstance(request_json, dict)
                requests.append(request_json)
                if len(requests) == 1:
                    return MockResponse({
                        "choices": [{"message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "get_trip_summary",
                                    "arguments": json.dumps({
                                        "start_date": "2026-07-01",
                                        "end_date": "2026-07-01",
                                    }),
                                },
                            }],
                        }}],
                    })
                return MockResponse({
                    "choices": [{"message": {"role": "assistant", "content": "There was 1 trip."}}],
                })

        monkeypatch.setattr("app.services.agent.httpx.AsyncClient", MockAsyncClient)
        context = AgentContext(
            scope="general",
            source_file="july.csv",
            completed_trips=1,
            delayed_trips=0,
            affected_employees=0,
            ota=100.0,
            ota_sla=90.0,
            attention_incidents=0,
            top_incidents=[],
            selected_incident=None,
        )
        config = Settings(
            database_url="sqlite://",
            ai_provider="sarvam",
            ai_api_key="test-key",
            ai_base_url="https://api.sarvam.ai",
            ai_model="sarvam-105b",
        )

        async def collect_response() -> str:
            return "".join([
                token
                async for token in _stream_sarvam(
                    MobilityAgentRequest(message="How many trips happened on 1 July 2026?"),
                    context,
                    config,
                    session,
                )
            ])

        assert asyncio.run(collect_response()) == "There was 1 trip."
        assert requests[0]["tool_choice"] == "auto"
        assert requests[0]["tools"][0]["function"]["name"] == "get_trip_summary"
        tool_message = requests[1]["messages"][-1]
        assert tool_message["role"] == "tool"
        assert tool_message["tool_call_id"] == "call-1"
        assert json.loads(tool_message["content"])["totalTrips"] == 1


def test_agent_analytics_tools_cover_daily_and_dimension_questions() -> None:
    engine = create_engine("sqlite://", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    config = Settings(database_url="sqlite://")
    trip_specs = [
        ("ZERO-1", datetime(2026, 7, 1, 9), 2, "Vendor A", "Route 1", "Morning"),
        ("ZERO-2", datetime(2026, 7, 1, 10), 3, "Vendor A", "Route 1", "Morning"),
        ("COUNT-1", datetime(2026, 7, 2, 9), 10, "Vendor B", "Route 2", "Night"),
        ("COUNT-2", datetime(2026, 7, 2, 10), 20, "Vendor B", "Route 2", "Night"),
        ("MAX-1", datetime(2026, 7, 3, 9), 30, "Vendor C", "Route 3", "Evening"),
    ]
    with Session(engine) as session:
        upload = DatasetUpload(filename="analytics.csv", valid_rows=5, invalid_rows=0, skipped_rows=0)
        session.add(upload)
        session.flush()
        session.add_all([
            Trip(
                dataset_upload_id=upload.id,
                trip_id=trip_id,
                vendor_id=vendor,
                route_id=route,
                shift_id=shift,
                employee_id=f"EMP-{trip_id}",
                transport_mode="CAB",
                scheduled_arrival=scheduled,
                actual_arrival=scheduled + timedelta(minutes=delay),
                status="completed",
                gps_available=True,
            )
            for trip_id, scheduled, delay, vendor, route, shift in trip_specs
        ])
        session.flush()
        impacted_trip = session.scalar(select(Trip).where(Trip.trip_id == "COUNT-1"))
        assert impacted_trip is not None
        impacted_trip.office_id = "Office A"
        impacted_trip.no_show_count = 2
        impacted_trip.delay_reason = "TRAFFIC"
        impacted_trip.driver_non_compliance = True
        session.add(SafetyAlert(
            trip_id="COUNT-1",
            employee_id="EMP-COUNT-1",
            event_id="alert-1",
            event_type="OVER_SPEEDING",
            started_at=datetime(2026, 7, 2, 9, 5),
            acknowledged_at=datetime(2026, 7, 2, 9, 10),
            state="CLOSED",
            severity="Sev-2",
            source="DEVICE",
        ))
        session.add(TripFeedback(
            trip_id="COUNT-1",
            employee_id="EMP-COUNT-1",
            trip_type="LOGIN",
            trip_at=datetime(2026, 7, 2, 9),
            route_rating=4,
            driver_rating=3,
            cab_rating=5,
            safety_rating=2,
            marshal_rating=0,
            created_at=datetime(2026, 7, 2, 12),
        ))
        session.commit()

        tool_names = {tool["function"]["name"] for tool in AGENT_TOOLS}
        assert len(tool_names) == 30
        assert {
            "get_trip_details",
            "get_trip_delays",
            "get_trip_statistics",
            "get_delay_by_vendor",
            "get_delay_by_office",
            "get_delay_by_shift",
            "get_vendor_performance",
            "compare_vendor_performance",
            "get_vendor_trips",
            "get_vendor_issues",
            "get_safety_alerts",
            "get_alert_details",
            "get_alerts_by_vendor",
            "get_alerts_by_office",
            "get_alerts_by_shift",
            "get_employee_impact",
            "get_no_show_statistics",
            "get_no_show_by_shift",
            "get_no_show_by_office",
            "get_feedback_summary",
            "get_feedback_by_vendor",
            "get_feedback_by_office",
            "get_historical_comparison",
            "compare_periods",
            "get_peer_comparison",
        } <= tool_names
        zero_days = execute_agent_tool(session, config, "get_zero_delay_dates", "{}")
        assert zero_days["dates"] == [{
            "date": "2026-07-01",
            "totalTrips": 2,
            "completedTrips": 2,
        }]

        highest_count = execute_agent_tool(session, config, "get_highest_delay_days", "{}")
        assert highest_count["days"][0]["date"] == "2026-07-02"
        assert highest_count["days"][0]["delayedTrips"] == 2
        highest_duration = execute_agent_tool(
            session,
            config,
            "get_highest_delay_days",
            json.dumps({"sort_by": "maximum_delay", "limit": 1}),
        )
        assert highest_duration["days"][0]["date"] == "2026-07-03"
        assert highest_duration["days"][0]["maximumDelayMinutes"] == 30.0

        for tool_name, result_key, id_key in [
            ("get_vendor_performance", "vendors", "vendorId"),
            ("get_route_performance", "routes", "routeId"),
            ("get_shift_performance", "shifts", "shiftId"),
        ]:
            result = execute_agent_tool(session, config, tool_name, "{}")
            assert result[result_key][0][id_key] in {"Vendor B", "Vendor C", "Route 2", "Route 3", "Night", "Evening"}
            assert result[result_key][0]["ota"] == 0.0

        alerts = execute_agent_tool(session, config, "get_safety_alerts", "{}")
        assert alerts["matchingAlerts"] == 1
        assert alerts["alerts"][0]["eventType"] == "OVER_SPEEDING"
        alert = execute_agent_tool(
            session,
            config,
            "get_alert_details",
            json.dumps({"event_id": "alert-1"}),
        )
        assert alert["alert"]["acknowledgementMinutes"] == 5.0

        employee_impact = execute_agent_tool(session, config, "get_employee_impact", "{}")
        assert employee_impact["noShowEmployees"] == 2
        assert employee_impact["employeesLinkedToSafetyAlerts"] == 1
        no_shows = execute_agent_tool(session, config, "get_no_show_by_office", "{}")
        assert no_shows["offices"][0]["officeId"] == "Office A"
        assert no_shows["offices"][0]["noShowEmployees"] == 2

        feedback = execute_agent_tool(session, config, "get_feedback_summary", "{}")
        assert feedback["responses"] == 1
        assert feedback["safetyAverage"] == 2.0
        assert feedback["marshalAverage"] is None

        comparison = execute_agent_tool(
            session,
            config,
            "compare_periods",
            json.dumps({
                "first_start_date": "2026-07-01",
                "first_end_date": "2026-07-01",
                "second_start_date": "2026-07-02",
                "second_end_date": "2026-07-02",
            }),
        )
        assert comparison["firstPeriod"]["ota"] == 100.0
        assert comparison["secondPeriod"]["ota"] == 0.0
        assert execute_agent_tool(session, config, "get_peer_comparison", "{}")["available"] is False
