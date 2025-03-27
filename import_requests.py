import requests
import uuid  # to generate a unique reference
from datetime import datetime, timedelta

################################################
# Start Authentication (Consent Flow)          #
################################################

# CORRECTED GoCardless API base URL (same for sandbox/production)
BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"

# Insert your actual sandbox user secret credentials from GoCardless
secret_id = "d927cff4-31b7-4573-9d63-876f478f1682"
secret_key = "cdf9e5b9fc409d86560b5cee565d1c48a3ccd2dd3fa8701e835ba4ce4303b7879577031c68b76a2c3caa179ccad1cf865b454090191ae364c8cb3e61ae59d209"

# Request access token
response = requests.post(
    f"{BASE_URL}/token/new/",
    headers={"Content-Type": "application/json"},
    json={
        "secret_id": secret_id,
        "secret_key": secret_key
    }
)

if response.status_code == 200:
    data = response.json()
    access_token = data["access"]
    print("✅ Access Token:", access_token)
else:
    print("❌ Error retrieving token:", response.status_code, response.text)
    exit()

################################################
# Optional: Create End User Agreement (90 days)  #
################################################

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

agreement_payload = {
    "institution_id": "SANDBOXFINANCE_SFIN0000",
    "max_historical_days": "90",
    "access_valid_for_days": "90",
    "access_scope": ["balances", "details", "transactions"]
}

agreement_response = requests.post(
    f"{BASE_URL}/agreements/enduser/",
    headers=headers,
    json=agreement_payload
)

# Debug: Print full agreement response
agreement_data = agreement_response.json()
print("Agreement response data:", agreement_data)

if "id" in agreement_data:
    agreement_id = agreement_data["id"]
    print("Agreement ID:", agreement_id)
else:
    print("❌ No 'id' found in agreement response. Exiting.")
    exit()

################################################
# Create Requisition (Generates Sandbox Link)  #
################################################

# Generate a unique reference using uuid
unique_reference = "test-reference-" + str(uuid.uuid4())

requisition_payload = {
    "redirect": "http://localhost:5000/callback",  # Update to your callback URL
    "institution_id": "SANDBOXFINANCE_SFIN0000",
    "reference": unique_reference,  # Unique reference for this requisition
    "agreement": agreement_id,  # Remove if not using a custom agreement
    "user_language": "EN"
}

requisition_response = requests.post(
    f"{BASE_URL}/requisitions/",
    headers=headers,
    json=requisition_payload
)

# Debug: Print full requisition response
print("Requisition status code:", requisition_response.status_code)
requisition_data = requisition_response.json()
print("Requisition response data:", requisition_data)

if "id" in requisition_data and "link" in requisition_data:
    requisition_id = requisition_data["id"]
    auth_link = requisition_data["link"]
    print("Requisition ID:", requisition_id)
    print("Auth link (open in browser to authorize):", auth_link)
else:
    print("❌ No 'id' or 'link' found in requisition response. Exiting.")
    exit()

################################################
# Wait for Manual Authorization Completion     #
################################################

# At this point, open the printed auth_link in your browser,
# complete the authentication process, and then come back to press Enter.
input("After completing the authorization in your browser, press Enter to continue...")

################################################
# List accounts (after manual authorization)   #
################################################

accounts_response = requests.get(
    f"{BASE_URL}/requisitions/{requisition_id}/",
    headers=headers
)

accounts_data = accounts_response.json()
print("Accounts response data:", accounts_data)

if "accounts" in accounts_data and accounts_data["accounts"]:
    accounts = accounts_data["accounts"]
    print("User's Account IDs:", accounts)
else:
    print("❌ No accounts linked. Make sure the authorization process was completed properly.")
    exit()

################################################
# Retrieve Transactions                        #
################################################

account_id = accounts[0]  # using first account for simplicity
end_date = datetime.now().date()
start_date = end_date - timedelta(days=90)

transactions_response = requests.get(
    f"{BASE_URL}/accounts/{account_id}/transactions/",
    headers=headers,
    params={
        "date_from": start_date.isoformat(),
        "date_to": end_date.isoformat()
    }
)

transactions_data = transactions_response.json()
print("Transactions response data:", transactions_data)

if "transactions" in transactions_data and "booked" in transactions_data["transactions"]:
    print("Transactions for account:", account_id)
    for txn in transactions_data["transactions"]["booked"]:
        print(f"Date: {txn['bookingDate']}, Amount: {txn['transactionAmount']['amount']} {txn['transactionAmount']['currency']}, Description: {txn.get('remittanceInformationUnstructured', 'N/A')}")
else:
    print("❌ No transactions data found for account", account_id)
