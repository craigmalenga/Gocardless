from flask import Flask, jsonify, request, render_template, session, redirect, url_for, send_file
import requests, uuid, sqlite3, tempfile
from datetime import datetime, timedelta
from fpdf import FPDF
import os
from io import StringIO, BytesIO
import csv


app = Flask(__name__)
app.secret_key = "super-secret-key"

# === Configuration ===
BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"
secret_id = "d927cff4-31b7-4573-9d63-876f478f1682"  # Replace with your actual production secret ID
secret_key = "cdf9e5b9fc409d86560b5cee565d1c48a3ccd2dd3fa8701e835ba4ce4303b7879577031c68b76a2c3caa179ccad1cf865b454090191ae364c8cb3e61ae59d209"  # Replace with your actual production secret key
DB_PATH = "category_keywords.db"

# === Categorisation Logic ===
def load_keywords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT keyword, category FROM keywords")
    keywords = cursor.fetchall()
    conn.close()
    return [(k.lower(), c) for k, c in keywords]

def categorise_transactions(transactions, keyword_map):
    for txn in transactions:
        description = txn.get("remittanceInformationUnstructured", "").lower()
        matched = False
        for keyword, category in keyword_map:
            if keyword in description:
                txn["category"] = category
                matched = True
                break
        if not matched:
            txn["category"] = "Other"
    return transactions

@app.route("/start-auth", methods=["GET"])
def start_auth():
    institution_id = request.args.get("institution_id")  # Get the selected institution ID from the query parameters
    if institution_id:
        # Step 1: Get access token
        token_response = requests.post(
            f"{BASE_URL}/token/new/",
            headers={"Content-Type": "application/json"},
            json={"secret_id": secret_id, "secret_key": secret_key}
        )
        if token_response.status_code != 200:
            return jsonify({"error": "Token failed", "details": token_response.text}), 400

        access_token = token_response.json()["access"]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Step 2: Create end user agreement
        agreement_payload = {
            "institution_id": institution_id,
            "max_historical_days": "180",  # Adjust the number of days based on your needs
            "access_valid_for_days": "30",  # Access validity period
            "access_scope": ["balances", "details", "transactions"]
        }
        agreement_response = requests.post(f"{BASE_URL}/agreements/enduser/", headers=headers, json=agreement_payload)
        agreement_data = agreement_response.json()
        agreement_id = agreement_data.get("id")
        if not agreement_id:
            return jsonify({"error": "Agreement failed", "details": agreement_data}), 400

        # Step 3: Create requisition (this generates the link for the user to authenticate)
        unique_reference = "real-ref-" + str(uuid.uuid4())
        requisition_payload = {
            "redirect": "http://localhost:5000/callback",  # Change this to your production callback URL
            "institution_id": institution_id,
            "reference": unique_reference,
            "agreement": agreement_id,
            "user_language": "EN"
        }
        requisition_response = requests.post(f"{BASE_URL}/requisitions/", headers=headers, json=requisition_payload)
        requisition_data = requisition_response.json()

        # Save requisition_id in session for later use
        requisition_id = requisition_data.get("id")
        session["requisition_id"] = requisition_id

        auth_link = requisition_data.get("link")
        if not auth_link:
            return jsonify({"error": "Requisition failed", "details": requisition_data}), 400

        return redirect(auth_link)

    return redirect(url_for("home"))  # If no institution selected, redirect back to home


@app.route("/callback")
def callback():
    requisition_id = session.get("requisition_id")
    if not requisition_id:
        return "Missing requisition_id in session. Please start again from the homepage.", 400

    # Step 1: Get access token again for authenticated requests
    token_response = requests.post(
        f"{BASE_URL}/token/new/",
        headers={"Content-Type": "application/json"},
        json={"secret_id": secret_id, "secret_key": secret_key}
    )
    if token_response.status_code != 200:
        return "Failed to get token", 500

    access_token = token_response.json()["access"]
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    # Step 2: Get accounts for the requisition
    req_info = requests.get(f"{BASE_URL}/requisitions/{requisition_id}/", headers=headers).json()
    account_ids = req_info.get("accounts", [])

    if not account_ids:
        return "No accounts linked. Try again."

    account_id = account_ids[0]  # First account only

    # Step 3: Fetch transactions for the account
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    txn_response = requests.get(
        f"{BASE_URL}/accounts/{account_id}/transactions/",
        headers=headers,
        params={
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat()
        }
    )

    txns = txn_response.json().get("transactions", {}).get("booked", [])

    # Save transactions in session for later use
    session["transactions"] = txns

    # Step 4: Display transactions
    return render_template("transactions.html", transactions=txns)

# Other routes like /download-pdf, /save-category, etc. remain the same

if __name__ == "__main__":
    app.run(debug=True, port=5000)
