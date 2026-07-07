#!/usr/bin/env python3
"""
Review Pulsator — Interactive AI Web Dashboard Server.
Serves a stunning, responsive frontend dashboard and REST API endpoints for visualizing
Swiggy sentiment trends, cluster metrics, and triggering live Groq LLM synthesis.
"""
import os
import sys
import json
import glob
import logging
from datetime import datetime, timezone
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Ensure review_pulsator is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from review_pulsator.config import PulsatorConfig
from review_pulsator.ingestion import IngestionService
from review_pulsator.clustering import ThemingEngine
from review_pulsator.synthesis import PulseGenerator
from review_pulsator.cli import run_pipeline

logger = logging.getLogger("dashboard_server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

PORT = int(os.getenv("PORT", 8080))
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD_DIR = os.path.join(os.path.dirname(ROOT_DIR), "frontend")
if not os.path.exists(DASHBOARD_DIR):
    DASHBOARD_DIR = os.path.join(ROOT_DIR, "frontend")


class PulsatorDashboardHandler(SimpleHTTPRequestHandler):
    """
    HTTP Request Handler serving static dashboard assets and REST API endpoints.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def _send_json(self, status_code: int, payload: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        if path == "/api/status":
            return self._handle_status()
        elif path == "/api/reports":
            return self._handle_list_reports()
        elif path == "/api/report":
            file_path = query.get("path", [""])[0]
            return self._handle_get_report(file_path)
        elif path == "/api/analytics":
            return self._handle_analytics()
        else:
            # Serve static files from dashboard dir if available, otherwise return API status
            if path == "/" or path == "/index.html":
                index_path = os.path.join(DASHBOARD_DIR, "index.html")
                if not os.path.exists(index_path):
                    return self._send_json(200, {
                        "status": "ONLINE",
                        "service": "Review Pulsator AI Engine Backend",
                        "message": "Backend REST API is running! Frontend is hosted on Vercel.",
                        "endpoints": ["/api/status", "/api/reports", "/api/analytics", "/api/trigger_pulse"]
                    })
                self.path = "/index.html"
            return super().do_GET()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/trigger_pulse":
            return self._handle_trigger_pulse()
        else:
            self._send_json(404, {"error": "Endpoint not found"})

    def _handle_status(self):
        config = PulsatorConfig.from_env()
        # Count archives
        archive_files = glob.glob(os.path.join(ROOT_DIR, "archives", "**", "*.json"), recursive=True)
        self._send_json(200, {
            "status": "ONLINE",
            "service": "Review Pulsator AI Engine",
            "version": "0.1.0",
            "model": config.groq_model,
            "temperature": config.groq_temperature,
            "word_ceiling": config.word_count_ceiling,
            "max_themes": config.max_themes,
            "target_email": config.target_email,
            "total_archived_reports": len(archive_files),
            "server_time": datetime.now(timezone.utc).isoformat()
        })

    def _handle_list_reports(self):
        reports = []
        search_dirs = [
            os.path.join(ROOT_DIR, "archives", "dry_run_reports"),
            os.path.join(ROOT_DIR, "archives", "delivered_reports"),
            os.path.join(ROOT_DIR, "archives")
        ]
        seen_paths = set()
        for d in search_dirs:
            if not os.path.exists(d):
                continue
            for f in os.listdir(d):
                if f.endswith(".json") and f.startswith("pulse_"):
                    full_p = os.path.join(d, f)
                    if full_p in seen_paths:
                        continue
                    seen_paths.add(full_p)
                    try:
                        with open(full_p, "r", encoding="utf-8") as file:
                            data = json.load(file)
                            reports.append({
                                "filename": f,
                                "path": os.path.relpath(full_p, ROOT_DIR),
                                "report_date": data.get("report_date", "Unknown Date"),
                                "word_count": data.get("word_count", 0),
                                "themes_count": len(data.get("top_themes", [])),
                                "status": data.get("status", "ARCHIVED"),
                                "top_themes": [t.get("name") for t in data.get("top_themes", [])]
                            })
                    except Exception as e:
                        logger.warning(f"Could not parse archive {full_p}: {e}")

        # Sort descending by date
        reports.sort(key=lambda x: x.get("report_date", ""), reverse=True)
        self._send_json(200, {"count": len(reports), "reports": reports})

    def _handle_get_report(self, rel_path: str):
        if not rel_path:
            # Return latest report if available
            search_dirs = [
                os.path.join(ROOT_DIR, "archives", "delivered_reports"),
                os.path.join(ROOT_DIR, "archives", "dry_run_reports"),
                os.path.join(ROOT_DIR, "archives")
            ]
            latest_file = None
            for d in search_dirs:
                if os.path.exists(d):
                    files = sorted([os.path.join(d, f) for f in os.listdir(d) if f.endswith(".json") and f.startswith("pulse_")], reverse=True)
                    if files:
                        latest_file = files[0]
                        break
            if not latest_file:
                return self._send_json(404, {"error": "No pulse reports generated yet. Click 'Trigger Live AI Pulse'!"})
            target_path = latest_file
        else:
            target_path = os.path.join(ROOT_DIR, rel_path)
            if not os.path.exists(target_path) or not os.path.abspath(target_path).startswith(ROOT_DIR):
                return self._send_json(404, {"error": f"Report file not found: {rel_path}"})

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._send_json(200, {"path": os.path.relpath(target_path, ROOT_DIR), "report": data})
        except Exception as e:
            self._send_json(500, {"error": f"Failed to read report: {str(e)}"})

    def _handle_analytics(self):
        input_path = os.path.join(ROOT_DIR, "data", "swiggy_reviews.json")
        if not os.path.exists(input_path):
            return self._send_json(404, {"error": "swiggy_reviews.json dataset not found"})

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                raw_reviews = json.load(f)

            play_count = sum(1 for r in raw_reviews if str(r.get("store") or r.get("store_type", "")).upper() in ("GOOGLE_PLAY", "GOOGLE PLAY"))
            app_store_count = sum(1 for r in raw_reviews if str(r.get("store") or r.get("store_type", "")).upper() in ("APP_STORE", "APPLE_APP_STORE", "APPLE APP STORE"))
            
            rating_dist = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            for r in raw_reviews:
                try:
                    rating = int(r.get("rating") or r.get("star_rating") or 3)
                except (ValueError, TypeError):
                    rating = 3
                if rating in rating_dist:
                    rating_dist[rating] += 1

            # Run clustering on the fly to get live theme distribution
            config = PulsatorConfig.from_env()
            ingestion = IngestionService()
            sanitized = ingestion.load_reviews_from_file(input_path)
            theming = ThemingEngine(config=config)
            clusters = theming.cluster_reviews(sanitized)

            theme_stats = []
            for c in clusters:
                theme_stats.append({
                    "id": c.theme_id,
                    "name": c.theme_name,
                    "count": c.review_count,
                    "severity": round(c.sentiment_severity_score, 2),
                    "avg_rating": c.average_rating,
                    "sample_quote": c.representative_quotes[0] if c.representative_quotes else "No quote"
                })

            self._send_json(200, {
                "total_raw": len(raw_reviews),
                "total_scrubbed_window": len(sanitized),
                "store_split": {
                    "google_play": play_count,
                    "apple_app_store": app_store_count
                },
                "rating_distribution": rating_dist,
                "themes": theme_stats,
                "recent_samples": [
                    {"store": r.get("store") or r.get("store_type"), "rating": r.get("rating") or r.get("star_rating"), "title": r.get("title"), "body": str(r.get("body", ""))[:120] + "..."}
                    for r in raw_reviews[:6]
                ]
            })
        except Exception as e:
            logger.exception("Error building analytics")
            self._send_json(500, {"error": str(e)})

    def _handle_trigger_pulse(self):
        logger.info("Live AI Pulse synthesis triggered from Web Dashboard...")
        try:
            input_path = os.path.join(ROOT_DIR, "data", "swiggy_reviews.json")
            res = run_pipeline(input_path=input_path, dry_run=False)
            self._send_json(200, {
                "success": True,
                "message": "Weekly Pulse Report synthesized and delivered via Google Workspace MCP!",
                "result": res
            })
        except Exception as e:
            logger.exception("Error triggering pulse")
            self._send_json(500, {"success": False, "error": str(e)})


def main():
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "archives"), exist_ok=True)
    os.makedirs(os.path.join(ROOT_DIR, "data"), exist_ok=True)
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, PulsatorDashboardHandler)
    print("=" * 70)
    print(f"🚀 REVIEW PULSATOR — INTERACTIVE AI WEB DASHBOARD ONLINE")
    print("=" * 70)
    print(f"🌐 Dashboard URL: http://localhost:{PORT}/")
    print(f"📡 REST API Base: http://localhost:{PORT}/api/")
    print(f"📂 Serving static files from: {DASHBOARD_DIR}")
    print("=" * 70)
    print("Press Ctrl+C to stop server.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
