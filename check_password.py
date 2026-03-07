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
        cursor.execute('SELECT user_id, username, password_hash FROM users WHERE username = "alice"')
        result = cursor.fetchone()
        print('Alice user record:')
        print(result)
        
        # Test password verification
        from werkzeug.security import check_password_hash
        password = 'alice'
        is_valid = check_password_hash(result['password_hash'], password)
        print(f'\nPassword verification for "alice": {is_valid}')
        
finally:
    conn.close()
