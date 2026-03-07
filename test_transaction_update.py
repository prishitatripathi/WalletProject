import requests

base_url = 'http://localhost:8080'

# Login as alice
print("Logging in as alice...")
login_resp = requests.post(f'{base_url}/api/login', json={
    'username': 'alice',
    'password': 'alice'
})
login_data = login_resp.json()
print(f"Login balance: ${login_data['user']['balance']:.2f}\n")

user_id = login_data['user']['user_id']
wallet_id = login_data['user']['wallet_id']

# Create a test deposit
print("Creating $50 deposit transaction...")
txn_resp = requests.post(f'{base_url}/api/transaction', json={
    'user_id': user_id,
    'transaction_type': 'deposit',
    'amount': 50,
    'description': 'API deposit test'
})
txn_data = txn_resp.json()
print(f"Transaction response: {txn_data}")
print(f"New balance from API: ${txn_data['new_balance']:.2f}\n")

# Check balance via user endpoint
print("Checking balance via /api/user endpoint...")
user_resp = requests.get(f'{base_url}/api/user/{user_id}')
user_data = user_resp.json()
print(f"Balance from /api/user: ${user_data['balance']:.2f}\n")

# Check wallet stored balance
import pymysql
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1704',
    database='wallet_db',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cursor:
        cursor.execute('SELECT balance FROM wallets WHERE wallet_id = %s', (wallet_id,))
        result = cursor.fetchone()
        print(f"Stored balance in database: ${result["balance"]:.2f}")
finally:
    conn.close()
