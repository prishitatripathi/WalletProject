import requests
import json

# Test the API endpoints
base_url = 'http://localhost:8080'

# Test login
print("Testing login...")
login_resp = requests.post(f'{base_url}/api/login', json={
    'username': 'alice',
    'password': 'alice'
})
print(f"Login response: {login_resp.json()}")
login_data = login_resp.json()

if login_data['status'] == 'success':
    user = login_data['user']
    user_id = user['user_id']
    print(f"\nLogged in as {user['username']}, User ID: {user_id}")
    print(f"Login response balance: ${user['balance']}")
    
    # Test user data endpoint
    print("\nTesting /api/user/user_id endpoint...")
    user_resp = requests.get(f'{base_url}/api/user/{user_id}')
    print(f"User data response: {user_resp.json()}")
    
    # Test ledger endpoint
    print("\nTesting /api/ledger endpoint...")
    wallet_id = user['wallet_id']
    ledger_resp = requests.get(f'{base_url}/api/ledger/{wallet_id}')
    ledger_data = ledger_resp.json()
    print(f"Ledger has {len(ledger_data['transactions'])} transactions")
    for txn in ledger_data['transactions'][:3]:
        print(f"  - {txn['description']}: ${txn['amount']}")
