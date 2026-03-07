from werkzeug.security import generate_password_hash
import pymysql

# Generate new password hashes
passwords = {
    'alice': 'alice',
    'bob': 'bob',
    'admin': 'admin'
}

conn = pymysql.connect(
    host='localhost',
    user='root',
    password='1704',
    database='wallet_db',
    cursorclass=pymysql.cursors.DictCursor
)

try:
    with conn.cursor() as cursor:
        for user, pwd in passwords.items():
            hashed = generate_password_hash(pwd)
            cursor.execute('UPDATE users SET password_hash = %s WHERE username = %s', (hashed, user))
            print(f'Updated {user}')
        conn.commit()
        print('All passwords updated successfully!')
        
finally:
    conn.close()
