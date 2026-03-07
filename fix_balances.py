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
        # Get all wallets and recalculate their balances
        cursor.execute('SELECT wallet_id, user_id FROM wallets')
        wallets = cursor.fetchall()
        
        print('Recalculating balances for all wallets...\n')
        
        for wallet in wallets:
            wallet_id = wallet['wallet_id']
            user_id = wallet['user_id']
            
            # Calculate balance from transactions
            cursor.execute('''
                SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as calculated_balance
                FROM transactions
                WHERE sender_id = %s OR receiver_id = %s
            ''', (wallet_id, wallet_id, wallet_id, wallet_id))
            
            result = cursor.fetchone()
            calculated_balance = float(result['calculated_balance'])
            
            # Update stored balance
            cursor.execute('UPDATE wallets SET balance = %s WHERE wallet_id = %s', 
                          (calculated_balance, wallet_id))
            
            # Get user info
            cursor.execute('SELECT username FROM users WHERE user_id = %s', (user_id,))
            user = cursor.fetchone()
            
            print(f'Wallet {wallet_id} ({user["username"]}): Updated balance to ${calculated_balance:.2f}')
        
        conn.commit()
        print('\nAll balances recalculated and updated successfully!')
        
        # Verify
        print('\nFinal wallet balances:')
        cursor.execute('''
            SELECT u.username, w.wallet_id, w.balance
            FROM wallets w
            JOIN users u ON w.user_id = u.user_id
            ORDER BY w.wallet_id
        ''')
        wallets = cursor.fetchall()
        for wallet in wallets:
            print(f'  {wallet["username"]} (ID {wallet["wallet_id"]}): ${wallet["balance"]:.2f}')
        
finally:
    conn.close()
