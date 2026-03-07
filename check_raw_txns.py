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
        cursor.execute('SELECT COUNT(*) as count FROM transactions')
        result = cursor.fetchone()
        print(f'Total transactions: {result["count"]}')

        cursor.execute('SELECT * FROM transactions ORDER BY created_at DESC')
        transactions = cursor.fetchall()
        print('Raw transactions table:')
        for txn in transactions:
            print(txn)

finally:
    conn.close()