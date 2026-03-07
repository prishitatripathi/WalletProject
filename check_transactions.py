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
        cursor.execute('''
            SELECT t.txn_id, t.sender_id, t.receiver_id, t.amount, t.description,
                   ws.user_id as sender_user, wr.user_id as receiver_user,
                   su.username as sender_name, ru.username as receiver_name
            FROM transactions t
            JOIN wallets ws ON t.sender_id = ws.wallet_id
            JOIN users su ON ws.user_id = su.user_id
            JOIN wallets wr ON t.receiver_id = wr.wallet_id
            JOIN users ru ON wr.user_id = ru.user_id
            ORDER BY t.created_at DESC
        ''')
        transactions = cursor.fetchall()
        print('All transactions:')
        for txn in transactions:
            print(f'ID {txn["txn_id"]}: {txn["sender_name"]} -> {txn["receiver_name"]}: ${txn["amount"]} ({txn["description"]})')

finally:
    conn.close()