import requests
import pymysql

base_url = 'http://localhost:8080'

# Get initial balances
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1704',
    database='wallet_db',
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cursor:
    cursor.execute('SELECT u.username, w.wallet_id, w.balance FROM users u JOIN wallets w ON u.user_id = w.user_id WHERE u.username IN ("alice", "bob")')
    results = cursor.fetchall()
    print("BEFORE TRANSFER:")
    for row in results:
        print(f"  {row['username']} (wallet {row['wallet_id']}): ${row['balance']:.2f}")

conn.close()

# Login as alice and transfer $100 to bob
print("\nPerforming $100 transfer from alice to bob...")
login_resp = requests.post(f'{base_url}/api/login', json={
    'username': 'alice',
    'password': 'alice'
})
alice_data = login_resp.json()['user']

txn_resp = requests.post(f'{base_url}/api/transaction', json={
    'user_id': alice_data['user_id'],
    'transaction_type': 'transfer',
    'amount': 100,
    'description': 'Transfer to bob for testing',
    'receiver_username': 'bob'
})

txn_data = txn_resp.json()
print(f"API response: {txn_data['message']}")
print(f"Alice new balance (from API): ${txn_data['new_balance']:.2f}")

# Check final balances in database
print("\nAFTER TRANSFER (from database):")
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1704',
    database='wallet_db',
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cursor:
    cursor.execute('SELECT u.username, w.wallet_id, w.balance FROM users u JOIN wallets w ON u.user_id = w.user_id WHERE u.username IN ("alice", "bob") ORDER BY u.username')
    results = cursor.fetchall()
    for row in results:
        print(f"  {row['username']} (wallet {row['wallet_id']}): ${row['balance']:.2f}")

conn.close()

print("\n✓ If both alice and bob balances were updated, the feature is working!")
