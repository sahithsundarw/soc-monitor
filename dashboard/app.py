"""Flask web dashboard for the SOC Monitor.

Concept: HTTP at the application layer. The browser polls JSON endpoints with GET
once a second (no websockets) and sends control actions with POST. Every JSON
response has the same shape: {"data": ..., "error": null | "message"}.
"""

import logging
import threading
from typing import Any

from flask import Flask, jsonify, render_template, request
from flask.typing import ResponseReturnValue
from werkzeug.serving import make_server

from dashboard.inspector import describe_layers
from datalink.crc import CRC_POLYNOMIALS
from datalink.framing import FRAMING_METHODS
from network.routing import build_forwarding_table
from soc.sensor import ATTACKS
from soc.system import SocSystem

logger = logging.getLogger("dashboard")

FLOOD_FRAMES = 150
SPOOF_FRAMES = 10
SPOOF_IP = "203.0.113.66"
RECENT_ALERTS = 30

# Where each node is drawn on the topology diagram (an 800 x 420 canvas).
NODE_POSITIONS = {
    "S1": (90, 90),
    "S2": (90, 210),
    "S3": (90, 330),
    "R1": (300, 150),
    "R2": (470, 90),
    "R3": (300, 330),
    "R4": (520, 280),
    "SOC": (710, 190),
}


class ApiError(Exception):
    """A request the dashboard cannot carry out; becomes a 400 response."""


def ok(data: Any) -> ResponseReturnValue:
    """Successful JSON response."""
    return jsonify({"data": data, "error": None})


def fail(message: str, status: int = 400) -> ResponseReturnValue:
    """Error JSON response with a readable message."""
    return jsonify({"data": None, "error": message}), status


def body() -> dict[str, Any]:
    """The JSON body of a POST request (empty dict if there is none)."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object")
    return data


def status_payload(system: SocSystem) -> dict[str, Any]:
    """Everything the top bar and Overview tab show."""
    totals = system.state.totals()
    firewall = system.firewall.stats()
    settings = system.settings
    return {
        "running": system.running,
        "tiles": {
            "events": totals["good"],
            "alerts": system.alerts.total,
            "corrupted": totals["corrupted"],
            "retransmissions": totals["retransmitted"],
            "firewall_blocks": firewall["blocked"],
        },
        "lost": totals["lost"],
        "alerts": system.alerts.recent()[:RECENT_ALERTS],
        "protocols": system.state.protocol_totals(),
        "per_sensor": system.state.counts(),
        "qos": {
            "timeline": system.policer.timeline(),
            "totals": system.policer.totals(),
        },
        "routes": system.routes(),
        "settings": {
            "method": settings.frame_format.method,
            "crc_type": settings.frame_format.crc_type,
            "error_rate": settings.error_rate,
        },
    }


def topology_payload(system: SocSystem) -> dict[str, Any]:
    """Nodes, links, routes and every router's forwarding table."""
    nodes = []
    for node_id, node in system.config["nodes"].items():
        x, y = NODE_POSITIONS.get(node_id, (400, 210))
        nodes.append(
            {
                "id": node_id,
                "name": node["name"],
                "role": node["role"],
                "sim_ip": node["sim_ip"],
                "x": x,
                "y": y,
            }
        )
    links = [
        {"a": a, "b": b, "cost": cost, "up": up}
        for a, b, cost, up in system.topology.links()
    ]
    tables = {
        router: build_forwarding_table(system.topology, router)
        for router in system.router_ids
    }
    return {
        "nodes": nodes,
        "links": links,
        "routes": system.routes(),
        "tables": tables,
        "destinations": system.topology.node_ids(),
    }


def event_summaries(system: SocSystem) -> list[dict[str, Any]]:
    """Short rows for the Packet Inspector's event list."""
    return [
        {
            "id": record["id"],
            "received_at": record["received_at"],
            "sensor": record["header"]["src_id"],
            "type": record["payload"]["type"],
            "protocol": record["protocol"],
        }
        for record in system.state.recent_events()
    ]


def find_event(system: SocSystem, event_id: str) -> dict[str, Any]:
    """Look up a recent event by id."""
    for record in system.state.recent_events():
        if record["id"] == event_id:
            return record
    raise ApiError(f"Event {event_id} is no longer in the recent list")


def require_sensor(system: SocSystem, sensor_id: Any) -> str:
    """Validate a sensor id from a request."""
    if sensor_id not in system.sensors:
        raise ApiError(f"Unknown sensor {sensor_id!r}")
    return sensor_id


def register_api(app: Flask, system: SocSystem) -> None:
    """Add the JSON endpoints."""

    @app.errorhandler(ApiError)
    def api_error(error: ApiError) -> ResponseReturnValue:
        return fail(str(error))

    @app.get("/api/status")
    def get_status() -> ResponseReturnValue:
        return ok(status_payload(system))

    @app.get("/api/topology")
    def get_topology() -> ResponseReturnValue:
        return ok(topology_payload(system))

    @app.get("/api/events")
    def get_events() -> ResponseReturnValue:
        return ok(event_summaries(system))

    @app.get("/api/events/<event_id>")
    def get_event(event_id: str) -> ResponseReturnValue:
        return ok(describe_layers(find_event(system, event_id)))

    @app.post("/api/links/<action>")
    def change_link(action: str) -> ResponseReturnValue:
        data = body()
        a, b = data.get("a"), data.get("b")
        try:
            if action == "fail":
                system.topology.fail_link(a, b)
            elif action == "restore":
                system.topology.restore_link(a, b)
            else:
                raise ApiError(f"Unknown link action {action!r}")
        except (ValueError, TypeError) as error:
            raise ApiError(str(error)) from error
        return ok({"a": a, "b": b, "up": action == "restore"})

    @app.post("/api/noise")
    def set_noise() -> ResponseReturnValue:
        try:
            error_rate = float(body().get("error_rate"))
            system.settings.set_error_rate(error_rate)
        except (ValueError, TypeError) as error:
            raise ApiError("error_rate must be a number between 0 and 1") from error
        return ok({"error_rate": error_rate})

    @app.post("/api/settings")
    def set_link_settings() -> ResponseReturnValue:
        data = body()
        try:
            if "method" in data:
                system.settings.set_method(data["method"])
            if "crc_type" in data:
                system.settings.set_crc_type(data["crc_type"])
        except ValueError as error:
            raise ApiError(str(error)) from error
        frame_format = system.settings.frame_format
        return ok({"method": frame_format.method, "crc_type": frame_format.crc_type})

    @app.post("/api/attack")
    def launch_attack() -> ResponseReturnValue:
        data = body()
        attack = data.get("attack")
        if attack not in ATTACKS:
            raise ApiError(f"Unknown attack {attack!r}")
        default_sensor = {"brute_force": "S3", "port_scan": "S2", "beacon": "S2"}
        sensor_id = require_sensor(system, data.get("sensor", default_sensor[attack]))
        system.sensors[sensor_id].launch(attack)
        return ok({"attack": attack, "sensor": sensor_id})

    @app.post("/api/flood")
    def flood() -> ResponseReturnValue:
        data = body()
        sensor = system.sensors[require_sensor(system, data.get("sensor"))]
        spoof = bool(data.get("spoof"))
        count = SPOOF_FRAMES if spoof else FLOOD_FRAMES
        threading.Thread(
            target=sensor.flood,
            args=(count, SPOOF_IP if spoof else ""),
            daemon=True,
        ).start()
        return ok({"sensor": sensor.node_id, "frames": count, "spoofed": spoof})


def create_app(system: SocSystem) -> Flask:
    """Build the Flask application for a (started or stopped) SOC system."""
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        """Serve the single-page dashboard."""
        return render_template(
            "index.html",
            sensors=system.sensor_ids,
            methods=FRAMING_METHODS,
            crc_types=list(CRC_POLYNOMIALS),
        )

    register_api(app, system)
    return app


class DashboardServer:
    """Runs the Flask app in a background thread so it can be shut down cleanly."""

    def __init__(self, app: Flask, host: str, port: int) -> None:
        """Bind the HTTP server socket."""
        self._server = make_server(host, port, app, threaded=True)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="dashboard", daemon=True
        )

    def start(self) -> None:
        """Start answering HTTP requests."""
        self._thread.start()

    def stop(self) -> None:
        """Stop the HTTP server and wait for its thread."""
        self._server.shutdown()
        self._thread.join(timeout=5)
