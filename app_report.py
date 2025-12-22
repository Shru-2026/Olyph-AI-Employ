# app_report.py
import os
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_cors import CORS
from dotenv import load_dotenv

# -------------------------------------------------
# Explicit .env loading (Render Secret Files support)
# -------------------------------------------------
ENV_PATH = "/etc/secrets/.env"

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()  # local development fallback

# -------------------------------------------------
# Report-specific imports
# -------------------------------------------------
from report_agent import generate_report_bytes
from auth.auth import verify_user

# -------------------------------------------------
# Flask App Setup
# -------------------------------------------------
app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

# -------------------------------------------------
# Home Route
# -------------------------------------------------
@app.route('/')
def home():
    """
    Minimal homepage for the report service.
    """
    try:
        return render_template('index_emp.html')
    except Exception:
        return """
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>Olyph Report Service</title></head>
        <body>
            <h3>Olyph Report Backend</h3>
            <p>This service exposes report generation endpoints.</p>
        </body>
        </html>
        """

# -------------------------------------------------
# Authenticated Report API
# -------------------------------------------------
@app.route('/api/report', methods=['POST'])
def api_report():
    """
    POST JSON expected:
    {
      "username": "<username>",        # required
      "password": "<password>",        # required
      "sheet_id": "<spreadsheetId>",   # optional
      "sheet": 0 or "<sheet name>",    # optional
      "format": "csv" or "xlsx"        # optional (default: csv)
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        # ---------- Authentication ----------
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""

        if not username or not password:
            return jsonify({"error": "Authentication required (username + password)."}), 401

        if not verify_user(username, password):
            return jsonify({"error": "Invalid username or password."}), 401

        # ---------- Report parameters ----------
        sheet_id = data.get("sheet_id") or request.args.get("sheet_id")
        sheet = data.get("sheet", None)
        fmt = (data.get("format", "csv") or "csv").lower()

        # ---------- Generate report ----------
        bio, filename, mimetype = generate_report_bytes(
            sheet_id=sheet_id,
            sheet=sheet,
            fmt=fmt
        )

        return send_file(
            bio,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )

    except FileNotFoundError as e:
        print("❌ /api/report FileNotFoundError:", e)
        return jsonify({
            "error": (
                "Service account JSON not found. "
                "Ensure service_account.json is uploaded as a Render Secret File."
            )
        }), 500

    except PermissionError as e:
        print("❌ /api/report PermissionError:", e)
        return jsonify({
            "error": (
                "Permission denied. Ensure the Google Sheet is shared with "
                "the service account email and APIs are enabled."
            )
        }), 500

    except Exception as e:
        print("❌ /api/report error:", type(e).__name__, e)
        return jsonify({
            "error": f"Internal error: {type(e).__name__}: {str(e)}"
        }), 500

# -------------------------------------------------
# Lightweight Download Endpoint (optional token auth)
# -------------------------------------------------
@app.route('/download-report', methods=['GET'])
def download_report():
    """
    GET endpoint for quick downloads using env-configured sheet.
    Optional token protection via REPORT_USE_TOKEN.
    """
    token_required = os.environ.get("REPORT_USE_TOKEN", "false").lower() == "true"

    if token_required:
        token = request.args.get("token") or request.headers.get("X-REPORT-TOKEN")
        expected = os.environ.get("REPORT_ACCESS_TOKEN")
        if not (token and expected and token == expected):
            return abort(401)

    try:
        bio, filename, mimetype = generate_report_bytes(fmt="csv")
        return send_file(
            bio,
            as_attachment=True,
            download_name=filename,
            mimetype=mimetype
        )

    except Exception as e:
        print("❌ /download-report error:", type(e).__name__, e)
        return jsonify({
            "error": f"Internal error: {type(e).__name__}: {str(e)}"
        }), 500

# -------------------------------------------------
# App Runner
# -------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=True)
