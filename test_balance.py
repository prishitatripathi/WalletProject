import pymysql
import os
from decimal import Decimal

# Connect to database
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1704',
    database='wallet_db',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cursor:
        # Check current user balance calculation
        cursor.execute('''
            SELECT u.user_id, u.username, u.full_name,
                   COALESCE(SUM(CASE 
                       WHEN t.sender_id = w.wallet_id THEN -t.amount 
                       WHEN t.receiver_id = w.wallet_id THEN t.amount 
                       ELSE 0 END), 0) as calculated_balance
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            LEFT JOIN transactions t ON t.sender_id = w.wallet_id OR t.receiver_id = w.wallet_id
            WHERE u.username = 'alice'
            GROUP BY u.user_id, u.username, u.full_name, w.wallet_id
        ''')
        result = cursor.fetchone()
        print('User balance calculation:')
        print(f'Username: {result["username"]}')
        print(f'Calculated Balance: ${result["calculated_balance"]}')

        # Check recent transactions
        cursor.execute('''
            SELECT t.txn_id, t.amount, t.description, t.created_at,
                   s.username as sender_name, r.username as receiver_name
            FROM transactions t
            JOIN wallets ws ON t.sender_id = ws.wallet_id
            JOIN users s ON ws.user_id = s.user_id
            JOIN wallets wr ON t.receiver_id = wr.wallet_id
            JOIN users r ON wr.user_id = r.user_id
            WHERE s.username = 'alice' OR r.username = 'alice'
            ORDER BY t.created_at DESC
            LIMIT 5
        ''')
        transactions = cursor.fetchall()
        print(f'\nRecent transactions for alice ({len(transactions)} found):')
        for txn in transactions:
            print(f'  {txn["created_at"]}: {txn["description"]} - ${txn["amount"]}')

finally:
    conn.close()