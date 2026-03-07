import requests

base_url = 'http://localhost:8080'

# Login as alice
login_resp = requests.post(f'{base_url}/api/login', json={
    'username': 'alice',
    'password': 'alice'
})
login_data = login_resp.json()
user_id = login_data['user']['user_id']
balance_before = login_data['user']['balance']
print(f"Alice balance before: ${balance_before:.2f}")

# Create a withdrawal
print("\nCreating $100 withdrawal...")
txn_resp = requests.post(f'{base_url}/api/transaction', json={
    'user_id': user_id,
    'transaction_type': 'withdraw',
    'amount': 100,
    'description': 'Cash withdrawal'
})

if txn_resp.status_code == 200:
    txn_data = txn_resp.json()
    print(f"✓ Withdrawal successful")
    print(f"New balance: ${txn_data['new_balance']:.2f}")
    print(f"Expected: ${balance_before - 100:.2f}")
else:
    print(f"✗ Withdrawal failed: {txn_resp.json()}")

# Test transfer 
print("\n\nCreating $75 transfer to bob...")
txn_resp = requests.post(f'{base_url}/api/transaction', json={
    'user_id': user_id,
    'transaction_type': 'transfer',
    'amount': 75,
    'description': 'Payment to bob',
    'receiver_username': 'bob'
})

if txn_resp.status_code == 200:
    txn_data = txn_resp.json()
    print(f"✓ Transfer successful")
    print(f"Alice new balance: ${txn_data['new_balance']:.2f}")
else:
    print(f"✗ Transfer failed: {txn_resp.json()}")

# Verify bob's balance increased
print("\n\nVerifying bob received the transfer...")
bob_resp = requests.post(f'{base_url}/api/login', json={
    'username': 'bob',
    'password': 'bob'
})
bob_data = bob_resp.json()
print(f"Bob's balance: ${bob_data['user']['balance']:.2f}")
