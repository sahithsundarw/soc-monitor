"""Flask web dashboard for the SOC Monitor.

Concept: HTTP at the application layer. The browser sends GET requests and the
Flask server answers with HTML (and, from Phase 5, JSON polled every second).
"""

import logging

from flask import Flask, render_template

from config_loader import load_config

LOG_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)-16s  %(message)s"

logger = logging.getLogger("dashboard")


def create_app() -> Flask:
    """Build the Flask application and register its routes."""
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        """Serve the dashboard page."""
        return render_template("index.html")

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    dashboard_config = load_config()["services"]["dashboard"]
    host, port = dashboard_config["host"], dashboard_config["port"]
    logger.info("Dashboard running at http://%s:%s", host, port)
    create_app().run(host=host, port=port)
