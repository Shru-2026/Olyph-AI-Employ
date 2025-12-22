# report_agent.py
"""
Report agent for Olyph AI.

- Handles Google Service Account auth.
- Fetches Google Sheet into pandas DataFrame.
- Exposes helper to return CSV/XLSX as BytesIO for download or further processing.
"""

import os
import io
import json
from datetime import datetime

import pandas as pd
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import AuthorizedSession

# -------------------------------------------------
# Explicit .env loading (Render Secret Files support)
# -------------------------------------------------
ENV_PATH = "/etc/secrets/.env"

if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)
else:
    load_dotenv()  # local development fallback

# -------------------------------------------------
# Google API Scopes
# -------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

# -------------------------------------------------
# Google Service Account Credentials
# -------------------------------------------------
def _get_service_account_credentials():
    """
    Priority:
    1) GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT (optional, raw JSON)
    2) Render Secret File: /etc/secrets/service_account.json
    3) Local fallback: ./creds/service_account.json
    """

    # 1️⃣ Raw JSON from env (optional)
    content = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "").strip()
    if content:
        try:
            info = json.loads(content)
            print("🔐 Using GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT")
            return Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            raise RuntimeError(f"Invalid GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT: {e}")

    # 2️⃣ Render Secret File (PRIMARY)
    render_path = "/etc/secrets/service_account.json"
    if os.path.exists(render_path):
        print(f"🔐 Using Render Secret File: {render_path}")
        return Credentials.from_service_account_file(render_path, scopes=SCOPES)

    # 3️⃣ Local development fallback
    local_path = os.path.join(os.getcwd(), "creds", "service_account.json")
    if os.path.exists(local_path):
        print(f"🔐 Using local service account file: {local_path}")
        return Credentials.from_service_account_file(local_path, scopes=SCOPES)

    raise FileNotFoundError(
        "Service account credentials not found. "
        "Upload service_account.json to Render Secret Files "
        "or set GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT."
    )

# -------------------------------------------------
# GSpread Client Helper
# -------------------------------------------------
def get_gspread_client():
    """
    Create an authenticated gspread client using service account credentials.
    """
    creds = _get_service_account_credentials()
    client = gspread.Client(auth=creds)
    client.session = AuthorizedSession(creds)
    return client

# -------------------------------------------------
# Fetch Google Sheet → DataFrame
# -------------------------------------------------
def fetch_sheet_as_dataframe(
    sheet_id=None,
    sheet_name_or_index=None,
    value_render_option="FORMATTED_VALUE",
) -> pd.DataFrame:
    """
    Fetch a Google Sheet and return it as a pandas DataFrame.

    Fallbacks:
    - REPORT_SHEET_ID
    - REPORT_SHEET_NAME_OR_INDEX
    """

    if not sheet_id:
        sheet_id = os.getenv("REPORT_SHEET_ID", "").strip()
        if not sheet_id:
            raise ValueError("No sheet_id provided and REPORT_SHEET_ID not set.")

    # Resolve worksheet name/index
    if sheet_name_or_index is None:
        env_sheet = os.getenv("REPORT_SHEET_NAME_OR_INDEX", "").strip()
        if env_sheet:
            try:
                sheet_name_or_index = int(env_sheet)
            except ValueError:
                sheet_name_or_index = env_sheet
        else:
            sheet_name_or_index = 0

    client = get_gspread_client()
    spreadsheet = client.open_by_key(sheet_id)

    if isinstance(sheet_name_or_index, int):
        worksheet = spreadsheet.get_worksheet(sheet_name_or_index)
    else:
        worksheet = spreadsheet.worksheet(sheet_name_or_index)

    values = worksheet.get_all_values()
    if not values:
        return pd.DataFrame()

    header = values[0]
    rows = values[1:]
    return pd.DataFrame(rows, columns=header)

# -------------------------------------------------
# DataFrame → Bytes Helpers
# -------------------------------------------------
def dataframe_to_csv_bytes(df: pd.DataFrame):
    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return buf

def dataframe_to_excel_bytes(df: pd.DataFrame):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")
    buf.seek(0)
    return buf

# -------------------------------------------------
# Main Report Generator
# -------------------------------------------------
def generate_report_bytes(sheet_id=None, sheet=None, fmt="csv"):
    """
    Returns:
        (BytesIO, filename, mimetype)
    """

    df = fetch_sheet_as_dataframe(sheet_id=sheet_id, sheet_name_or_index=sheet)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    chosen_id = sheet_id or os.getenv("REPORT_SHEET_ID", "unknown")

    fmt_lower = fmt.lower()
    if fmt_lower in ("csv", "text/csv"):
        bio = dataframe_to_csv_bytes(df)
        filename = f"sheet_{chosen_id}_{timestamp}.csv"
        mimetype = "text/csv"

    elif fmt_lower in ("xlsx", "excel"):
        bio = dataframe_to_excel_bytes(df)
        filename = f"sheet_{chosen_id}_{timestamp}.xlsx"
        mimetype = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        raise ValueError("Unsupported format. Use 'csv' or 'xlsx'.")

    return bio, filename, mimetype
