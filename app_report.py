# app_report.py
import os
from flask import Flask, render_template, request, jsonify, send_file, abort
from flask_cors import CORS
from dotenv import load_dotenv

# Report-specific imports
from report_agent import generate_report_bytes
from auth.auth import verify_user

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)


@app.route('/')
def home():
    # Minimal homepage for the report service
    try:
        # if you have a dedicated report template, use it (e.g. templates/report_home.html)
        return render_template('index_emp.html')
    except Exception:
        return """
        <!doctype html><html><head><meta charset="utf-8"><title>Olyph Report Service</title></head>
        <body><h3>Olyph Report Backend</h3>
        <p>This service exposes report generation endpoints.</p></body></html>
        """


@app.route('/api/report', methods=['POST'])
def api_report():
    """
    POST JSON expected:
    {
      "username": "<username>",        # required
      "password": "<password>",        # required
      "sheet_id": "<spreadsheetId>",   # optional - falls back to REPORT_SHEET_ID env
      "sheet": 0 or "<sheet name>",    # optional
      "format": "csv" or "xlsx"        # optional, default csv
    }
    """
    try:
        data = request.get_json(silent=True) or {}

        # --- Authentication ---
        username = (data.get("username") or "").strip()
        password = data.get("password") or ""
        if not username or not password:
            return jsonify({"error": "Authentication required (username + password)."}), 401

        if not verify_user(username, password):
            return jsonify({"error": "Invalid username or password."}), 401

        # --- Report parameters ---
        sheet_id = data.get("sheet_id") or request.args.get("sheet_id")
        sheet = data.get("sheet", None)
        fmt = (data.get("format", "csv") or "csv").lower()

        # Generate and return file (report_agent should return an io.BytesIO or file-like)
        bio, filename, mimetype = generate_report_bytes(sheet_id=sheet_id, sheet=sheet, fmt=fmt)
        return send_file(bio, as_attachment=True, download_name=filename, mimetype=mimetype)

    except FileNotFoundError as e:
        msg = "Service account JSON not found. Ensure GOOGLE_SERVICE_ACCOUNT_JSON or creds/service_account.json exists."
        print("❌ /api/report FileNotFoundError:", e)
        return jsonify({"error": msg}), 500
    except PermissionError as e:
        print("❌ /api/report PermissionError:", e)
        msg = ("Permission denied. Check that the service account JSON file is readable by the server "
               "and that the spreadsheet is shared with the service account email. "
               "Also confirm Google Sheets API & Drive API are enabled.")
        return jsonify({"error": msg}), 500
    except Exception as e:
        print("❌ /api/report error:", type(e).__name__, e)
        return jsonify({"error": f"Internal error: {type(e).__name__}: {str(e)}"}), 500


@app.route('/download-report', methods=['GET'])
def download_report():
    """
    lightweight GET endpoint for quick downloads using default env-configured sheet.
    Note: This endpoint currently does not authenticate; consider adding token auth if needed.
    """
    # OPTIONAL: protect this endpoint with token check:
    token_required = os.environ.get("REPORT_USE_TOKEN", "false").lower() == "true"
    if token_required:
        token = request.args.get("token") or request.headers.get("X-REPORT-TOKEN")
        expected = os.environ.get("REPORT_ACCESS_TOKEN")
        if not (token and expected and token == expected):
            return abort(401)

    try:
        bio, filename, mimetype = generate_report_bytes(fmt="csv")
        return send_file(bio, as_attachment=True, download_name=filename, mimetype=mimetype)
    except Exception as e:
        print("❌ /download-report error:", type(e).__name__, e)
        return jsonify({"error": f"Internal error: {type(e).__name__}: {str(e)}"}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Run report-only service
    app.run(host='0.0.0.0', port=port, debug=True)
