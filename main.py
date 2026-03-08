
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Optional
from fastapi import Query
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get database config from environment variables (for cloud deployment)
DB_TYPE = os.environ.get('DB_TYPE', 'mysql').lower()

DB_CONFIG = {
    'host': os.environ.get('DB_HOST', '127.0.0.1'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '1704'),
    'database': os.environ.get('DB_NAME', 'wallet_db')
}

# Import appropriate database library based on DB_TYPE
if DB_TYPE == 'postgres' or DB_TYPE == 'postgresql':
    import psycopg2
    import psycopg2.extras
    def get_db_connection():
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        return conn
    SQL_DIALECT = 'postgres'
    print("Using PostgreSQL database")
else:
    # Default to MySQL
    import pymysql
    import pymysql.cursors
    def get_db_connection():
        return pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    SQL_DIALECT = 'mysql'
    print("Using MySQL database")

# Get cursor function
def get_cursor(conn):
    if SQL_DIALECT == 'postgres':
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        return conn.cursor()

# Initialize database tables
def init_db():
    conn = None
    try:
        conn = get_db_connection()
        cursor = get_cursor(conn)
        
        if SQL_DIALECT == 'postgres':
            # PostgreSQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    full_name VARCHAR(100) NOT NULL,
                    role VARCHAR(20) DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS wallets (
                    wallet_id SERIAL PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    balance DECIMAL(18, 2) DEFAULT 0.00,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    txn_id SERIAL PRIMARY KEY,
                    sender_id INT,
                    receiver_id INT,
                    amount DECIMAL(18, 2) NOT NULL,
                    description VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS money_requests (
                    request_id SERIAL PRIMARY KEY,
                    requester_id INT NOT NULL,
                    payee_id INT NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    description VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # MySQL schema
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS money_requests (
                    request_id INT AUTO_INCREMENT PRIMARY KEY,
                    requester_id INT NOT NULL,
                    payee_id INT NOT NULL,
                    amount DECIMAL(15,2) NOT NULL,
                    description VARCHAR(255),
                    status ENUM('pending','approved','denied') NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (requester_id) REFERENCES wallets(wallet_id),
                    FOREIGN KEY (payee_id) REFERENCES wallets(wallet_id)
                ) ENGINE=InnoDB
            """)
        
        conn.commit()
        print("Database initialized successfully")
        
        # Create test users if they don't exist
        cursor.execute("SELECT COUNT(*) as count FROM users")
        if cursor.fetchone()['count'] == 0:
            # Insert test users with hashed passwords (password = "password")
            admin_hash = generate_password_hash("password")
            alice_hash = generate_password_hash("password")
            bob_hash = generate_password_hash("password")
            
            if SQL_DIALECT == 'postgres':
                # Insert test users one by one to get their IDs properly
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, role) VALUES 
                    (%s, %s, %s, %s) RETURNING user_id
                """, ('admin', admin_hash, 'System Administrator', 'admin'))
                admin_id = cursor.fetchone()['user_id']
                
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, role) VALUES 
                    (%s, %s, %s, %s) RETURNING user_id
                """, ('alice', alice_hash, 'Alice Vance', 'user'))
                alice_id = cursor.fetchone()['user_id']
                
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, role) VALUES 
                    (%s, %s, %s, %s) RETURNING user_id
                """, ('bob', bob_hash, 'Robert Fox', 'user'))
                bob_id = cursor.fetchone()['user_id']
                
                # Create wallets for each user
                cursor.execute("INSERT INTO wallets (user_id, balance) VALUES (%s, %s)", (admin_id, 1000.00))
                cursor.execute("INSERT INTO wallets (user_id, balance) VALUES (%s, %s)", (alice_id, 1000.00))
                cursor.execute("INSERT INTO wallets (user_id, balance) VALUES (%s, %s)", (bob_id, 1000.00))
                
                # Add initial transaction
                cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (admin_id,))
                admin_wallet = cursor.fetchone()
                cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (alice_id,))
                alice_wallet = cursor.fetchone()
                
                if admin_wallet and alice_wallet:
                    cursor.execute("""
                        INSERT INTO transactions (sender_id, receiver_id, amount, description)
                        VALUES (%s, %s, %s, %s)
                    """, (admin_wallet['wallet_id'], alice_wallet['wallet_id'], 500.00, 'Welcome Bonus'))
            else:
                cursor.execute("""
                    INSERT INTO users (username, password_hash, full_name, role) VALUES 
                    (%s, %s, %s, %s), (%s, %s, %s, %s), (%s, %s, %s, %s)
                """, ('admin', admin_hash, 'System Administrator', 'admin',
                      'alice', alice_hash, 'Alice Vance', 'user',
                      'bob', bob_hash, 'Robert Fox', 'user'))
                
                # Get user IDs
                cursor.execute("SELECT user_id FROM users ORDER BY user_id")
                user_ids = cursor.fetchall()
                
                # Create wallets
                for uid in user_ids:
                    cursor.execute("INSERT INTO wallets (user_id, balance) VALUES (%s, %s)", 
                                  (uid['user_id'], 1000.00))
                
                # Add initial transactions
                cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = 1")
                admin_wallet = cursor.fetchone()
                cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = 2")
                alice_wallet = cursor.fetchone()
                
                if admin_wallet and alice_wallet:
                    cursor.execute("""
                        INSERT INTO transactions (sender_id, receiver_id, amount, description)
                        VALUES (%s, %s, %s, %s)
                    """, (admin_wallet['wallet_id'], alice_wallet['wallet_id'], 500.00, 'Welcome Bonus'))
            
            conn.commit()
            print("Test users created: admin, alice, bob (password: password)")
    except Exception as e:
        print(f"DB init error: {e}")
    finally:
        if conn:
            conn.close()

# Initialize on startup
init_db()

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    full_name: str

class TransactionRequest(BaseModel):
    user_id: int
    receiver_username: Optional[str] = None
    amount: float
    description: str
    transaction_type: str

class ApproveRequest(BaseModel):
    request_id: int
    user_id: int

class ReverseRequest(BaseModel):
    transaction_id: int
    user_id: int

def execute_query(query, params=None, fetch=True):
    """Helper function to execute queries with the correct database"""
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute(query, params or ())
        if fetch:
            result = cursor.fetchall()
            conn.commit()
            return result
        else:
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()

@app.post("/api/login")
async def login(req: LoginRequest):
    try:
        query = """
            SELECT u.user_id, u.username, u.full_name, u.role, u.password_hash, w.wallet_id
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            WHERE u.username = %s
        """
        users = execute_query(query, (req.username,))
        if not users:
            raise HTTPException(status_code=401, detail="Invalid Credentials")
        
        user = users[0]
        if 'password_hash' in user and check_password_hash(user['password_hash'], req.password):
            # Get calculated balance
            balance_query = """
                SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as balance
                FROM transactions
                WHERE sender_id = %s OR receiver_id = %s
            """
            balance_results = execute_query(balance_query, (user['wallet_id'], user['wallet_id'], user['wallet_id'], user['wallet_id']))
            balance = float(balance_results[0]['balance']) if balance_results else 0.0
            
            # Update stored balance
            execute_query("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (balance, user['wallet_id']), fetch=False)
            
            return {
                "status": "success",
                "user": {
                    "user_id": user['user_id'],
                    "username": user['username'],
                    "full_name": user['full_name'],
                    "role": user['role'],
                    "wallet_id": user['wallet_id'],
                    "balance": balance
                }
            }
        raise HTTPException(status_code=401, detail="Invalid Credentials")
    except HTTPException:
        raise
    except Exception as err:
        print(f"Database Error: {err}")
        raise HTTPException(status_code=500, detail="Database connection failed")

@app.post("/api/register")
async def register(req: RegisterRequest):
    try:
        # Check if username exists
        users = execute_query("SELECT user_id FROM users WHERE username = %s", (req.username,))
        if users:
            raise HTTPException(status_code=400, detail="Username already exists")
        
        # Hash password
        password_hash = generate_password_hash(req.password)
        
        # Insert user
        if SQL_DIALECT == 'postgres':
            user_id = execute_query(
                "INSERT INTO users (username, password_hash, full_name) VALUES (%s, %s, %s) RETURNING user_id",
                (req.username, password_hash, req.full_name)
            )
            user_id = user_id[0]['user_id'] if user_id else None
        else:
            execute_query(
                "INSERT INTO users (username, password_hash, full_name) VALUES (%s, %s, %s)",
                (req.username, password_hash, req.full_name)
            )
            # Get the last insert id
            result = execute_query("SELECT LAST_INSERT_ID() as user_id")
            user_id = result[0]['user_id']
        
        # Create wallet
        execute_query("INSERT INTO wallets (user_id) VALUES (%s)", (user_id,))
        
        return {"status": "success", "message": "User registered successfully"}
    except HTTPException:
        raise
    except Exception as err:
        print(f"Registration Error: {err}")
        raise HTTPException(status_code=500, detail="Registration failed")

@app.post("/api/transaction")
async def create_transaction(req: TransactionRequest):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        # Get user's wallet
        cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (req.user_id,))
        wallet = cursor.fetchone()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        wallet_id = wallet['wallet_id']
        receiver_wallet_id = None
        
        # Get current balance
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as current_balance
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        
        balance_result = cursor.fetchone()
        current_balance = float(balance_result['current_balance']) if balance_result else 0.0
        
        if req.transaction_type == 'deposit':
            cursor.execute(
                "INSERT INTO transactions (receiver_id, amount, description) VALUES (%s, %s, %s)",
                (wallet_id, req.amount, req.description)
            )
        elif req.transaction_type == 'withdraw':
            if current_balance < req.amount:
                raise HTTPException(status_code=400, detail="Insufficient funds")
            cursor.execute(
                "INSERT INTO transactions (sender_id, amount, description) VALUES (%s, %s, %s)",
                (wallet_id, req.amount, req.description)
            )
        elif req.transaction_type == 'transfer':
            if not req.receiver_username:
                raise HTTPException(status_code=400, detail="Receiver username required for transfer")
            
            cursor.execute("""
                SELECT w.wallet_id FROM wallets w
                JOIN users u ON w.user_id = u.user_id
                WHERE u.username = %s
            """, (req.receiver_username,))
            receiver_wallet = cursor.fetchone()
            if not receiver_wallet:
                raise HTTPException(status_code=404, detail="Receiver not found")
            
            if current_balance < req.amount:
                raise HTTPException(status_code=400, detail="Insufficient funds")
            
            receiver_wallet_id = receiver_wallet['wallet_id']
            cursor.execute(
                "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s, %s, %s, %s)",
                (wallet_id, receiver_wallet_id, req.amount, req.description)
            )
            txn_id = cursor.lastrowid
        elif req.transaction_type == 'request_money':
            if not req.receiver_username:
                raise HTTPException(status_code=400, detail="Receiver username required for request")
            
            cursor.execute("""
                SELECT w.wallet_id FROM wallets w
                JOIN users u ON w.user_id = u.user_id
                WHERE u.username = %s
            """, (req.receiver_username,))
            payee_wallet = cursor.fetchone()
            if not payee_wallet:
                raise HTTPException(status_code=404, detail="User not found")
            
            payee_wallet_id = payee_wallet['wallet_id']
            cursor.execute(
                "INSERT INTO money_requests (requester_id, payee_id, amount, description, status) VALUES (%s, %s, %s, %s, 'pending')",
                (wallet_id, payee_wallet_id, req.amount, req.description)
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid transaction type")
        
        conn.commit()
        
        # Get updated balance
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as new_balance
            FROM transactions 
            WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        result = cursor.fetchone()
        new_balance = float(result['new_balance']) if result else 0.0
        
        cursor.execute("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (new_balance, wallet_id))
        
        if receiver_wallet_id:
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as receiver_balance
                FROM transactions 
                WHERE sender_id = %s OR receiver_id = %s
            """, (receiver_wallet_id, receiver_wallet_id, receiver_wallet_id, receiver_wallet_id))
            receiver_result = cursor.fetchone()
            receiver_new_balance = float(receiver_result['receiver_balance']) if receiver_result else 0.0
            cursor.execute("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (receiver_new_balance, receiver_wallet_id))
        
        conn.commit()
        
        resp = {"status": "success", "message": "Transaction completed successfully", "new_balance": new_balance}
        if 'txn_id' in locals() and txn_id:
            resp['transaction_id'] = txn_id
        return resp
    except HTTPException:
        conn.rollback()
        raise
    except Exception as err:
        conn.rollback()
        print(f"Transaction Error: {err}")
        raise HTTPException(status_code=500, detail="Transaction failed")
    finally:
        cursor.close()
        conn.close()

@app.get("/api/ledger/{wallet_id}")
async def get_ledger(wallet_id: int):
    try:
        query = """
            SELECT t.*, 
                   su.full_name as sender_name, 
                   ru.full_name as receiver_name
            FROM transactions t
            LEFT JOIN wallets sw ON t.sender_id = sw.wallet_id
            LEFT JOIN users su ON sw.user_id = su.user_id
            LEFT JOIN wallets rw ON t.receiver_id = rw.wallet_id
            LEFT JOIN users ru ON rw.user_id = ru.user_id
            WHERE t.sender_id = %s OR t.receiver_id = %s 
            ORDER BY t.created_at DESC
        """
        transactions = execute_query(query, (wallet_id, wallet_id))
        return {"transactions": transactions}
    except Exception as err:
        print(f"Ledger Error: {err}")
        return {"transactions": []}

@app.get("/api/user/{user_id}")
async def get_user_data(user_id: int):
    try:
        query = """
            SELECT u.user_id, u.username, u.full_name, u.role, w.wallet_id,
                   COALESCE(SUM(CASE WHEN t.receiver_id = w.wallet_id THEN t.amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN t.sender_id = w.wallet_id THEN t.amount ELSE 0 END), 0) as balance
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            LEFT JOIN transactions t ON t.sender_id = w.wallet_id OR t.receiver_id = w.wallet_id
            WHERE u.user_id = %s
            GROUP BY u.user_id, w.wallet_id
        """
        users = execute_query(query, (user_id,))
        if not users:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = users[0]
        execute_query("UPDATE wallets SET balance = %s WHERE user_id = %s", (user['balance'], user_id), fetch=False)
        return {"status": "success", "balance": float(user['balance'])}
    except HTTPException:
        raise
    except Exception as err:
        print(f"User Data Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to get user data")

@app.get("/api/users/search")
async def search_users(query: str):
    try:
        search_term = f"%{query}%"
        users = execute_query("""
            SELECT user_id, username, full_name FROM users 
            WHERE (username LIKE %s OR full_name LIKE %s) AND user_id != 0
            LIMIT 10
        """, (search_term, search_term))
        return {"status": "success", "users": users}
    except Exception as err:
        print(f"Search Error: {err}")
        return {"status": "error", "users": []}

@app.get("/api/admin/accounts")
async def admin_list_accounts(user_id: int):
    try:
        # Verify admin
        users = execute_query("SELECT role FROM users WHERE user_id = %s", (user_id,))
        if not users or users[0].get('role') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        accounts = execute_query("""
            SELECT u.user_id, u.username, u.full_name, u.role, w.wallet_id, w.balance
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            ORDER BY u.user_id ASC
        """)
        
        return {'status': 'success', 'accounts': [
            {
                'user_id': row['user_id'],
                'username': row['username'],
                'full_name': row['full_name'],
                'role': row['role'],
                'wallet_id': row['wallet_id'],
                'balance': float(row['balance']) if row['balance'] is not None else 0.0
            }
            for row in accounts
        ]}
    except HTTPException:
        raise
    except Exception as err:
        print(f"Admin accounts error: {err}")
        raise HTTPException(status_code=500, detail="Failed to fetch accounts")

@app.get("/api/stats")
async def get_stats(user_id: int):
    try:
        wallets = execute_query("SELECT wallet_id FROM wallets WHERE user_id = %s", (user_id,))
        if not wallets:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        wallet_id = wallets[0]['wallet_id']
        
        txn_count_result = execute_query("""
            SELECT COUNT(*) as count FROM transactions WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id))
        txn_count = txn_count_result[0]['count']
        
        result = execute_query("""
            SELECT 
                COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) as total_received,
                COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as total_sent
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        
        return {
            "status": "success",
            "total_transactions": txn_count,
            "total_received": float(result[0]['total_received']),
            "total_sent": float(result[0]['total_sent']),
            "net": float(result[0]['total_received']) - float(result[0]['total_sent'])
        }
    except HTTPException:
        raise
    except Exception as err:
        print(f"Stats Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to get stats")

@app.get("/api/pending-requests/{wallet_id}")
async def get_pending_requests(wallet_id: int):
    try:
        reqs = execute_query("""
            SELECT r.request_id,
                   r.requester_id,
                   r.payee_id,
                   r.amount,
                   r.description,
                   r.created_at,
                   u.username,
                   u.full_name
            FROM money_requests r
            JOIN wallets w ON r.requester_id = w.wallet_id
            JOIN users u ON w.user_id = u.user_id
            WHERE r.payee_id = %s AND r.status = 'pending'
            ORDER BY r.created_at DESC
        """, (wallet_id,))
        
        return {
            "status": "success",
            "pending_requests": [
                {
                    "request_id": r['request_id'],
                    "from_user": r['username'],
                    "from_name": r['full_name'],
                    "amount": float(r['amount']),
                    "reason": r['description'],
                    "created_at": r['created_at'].isoformat() if r['created_at'] else None
                }
                for r in reqs
            ]
        }
    except Exception as err:
        print(f"Pending Requests Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to get pending requests")

@app.get("/api/transactions")
async def list_transactions(
    user_id: int,
    q: Optional[str] = Query(None),
    txn_type: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
    until: Optional[str] = Query(None),
    limit: int = 50
):
    try:
        # First get wallet_id
        wallets = execute_query("SELECT wallet_id FROM wallets WHERE user_id = %s", (user_id,))
        if not wallets:
            return {"status": "success", "transactions": []}
        
        wallet_id = wallets[0]['wallet_id']
        
        sql = """
            SELECT t.*, su.full_name as sender_name, ru.full_name as receiver_name
            FROM transactions t
            LEFT JOIN wallets sw ON t.sender_id = sw.wallet_id
            LEFT JOIN users su ON sw.user_id = su.user_id
            LEFT JOIN wallets rw ON t.receiver_id = rw.wallet_id
            LEFT JOIN users ru ON rw.user_id = ru.user_id
            WHERE (t.sender_id = %s OR t.receiver_id = %s)
        """
        params = [wallet_id, wallet_id]
        
        if q:
            sql += " AND (t.description LIKE %s OR su.username LIKE %s OR ru.username LIKE %s)"
            like = f"%{q}%"
            params.extend([like, like, like])
        
        if txn_type:
            if txn_type == 'debit':
                sql += " AND t.sender_id = %s"
                params.append(wallet_id)
            elif txn_type == 'credit':
                sql += " AND t.receiver_id = %s"
                params.append(wallet_id)
        
        if since:
            sql += " AND t.created_at >= %s"
            params.append(since)
        if until:
            sql += " AND t.created_at <= %s"
            params.append(until)
        
        sql += " ORDER BY t.created_at DESC LIMIT %s"
        params.append(limit)
        
        transactions = execute_query(sql, tuple(params))
        return {"status": "success", "transactions": transactions}
    except Exception as err:
        print(f"Transactions list error: {err}")
        raise HTTPException(status_code=500, detail="Failed to list transactions")

@app.get("/api/contacts")
async def recent_contacts(user_id: int, limit: int = 10):
    try:
        wallets = execute_query("SELECT wallet_id FROM wallets WHERE user_id = %s", (user_id,))
        if not wallets:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        wid = wallets[0]['wallet_id']
        
        contacts = execute_query("""
            SELECT DISTINCT
                CASE WHEN t.sender_id = %s THEN ru.username ELSE su.username END as username,
                CASE WHEN t.sender_id = %s THEN ru.full_name ELSE su.full_name END as full_name
            FROM transactions t
            LEFT JOIN wallets sw ON t.sender_id = sw.wallet_id
            LEFT JOIN users su ON sw.user_id = su.user_id
            LEFT JOIN wallets rw ON t.receiver_id = rw.wallet_id
            LEFT JOIN users ru ON rw.user_id = ru.user_id
            WHERE t.sender_id = %s OR t.receiver_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s
        """, (wid, wid, wid, wid, limit))
        
        return {"status": "success", "contacts": contacts}
    except HTTPException:
        raise
    except Exception as err:
        print(f"Contacts error: {err}")
        return {"status": "error", "contacts": []}

@app.post("/api/approve-request")
async def approve_request(req: ApproveRequest):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT * FROM money_requests WHERE request_id = %s", (req.request_id,))
        request_row = cursor.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request not found")
        if request_row['status'] != 'pending':
            raise HTTPException(status_code=400, detail="Request already processed")
        
        if request_row['payee_id'] != req.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to approve this request")
        
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END),0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END),0) as bal
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (req.user_id, req.user_id, req.user_id, req.user_id))
        bal_res = cursor.fetchone()
        payee_balance = float(bal_res['bal']) if bal_res else 0.0
        amount = float(request_row['amount'])
        if payee_balance < amount:
            raise HTTPException(status_code=400, detail="Insufficient funds to approve request")
        
        cursor.execute(
            "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s,%s,%s,%s)",
            (request_row['payee_id'], request_row['requester_id'], amount, request_row['description'])
        )
        
        cursor.execute("UPDATE money_requests SET status='approved' WHERE request_id=%s", (req.request_id,))
        conn.commit()
        
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END),0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END),0) as balance
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (req.user_id, req.user_id, req.user_id, req.user_id))
        payee_new = cursor.fetchone()['balance']
        
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END),0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END),0) as balance
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (request_row['requester_id'], request_row['requester_id'], request_row['requester_id'], request_row['requester_id']))
        requester_new = cursor.fetchone()['balance']
        
        return {"status":"success","payee_new_balance":float(payee_new),"requester_new_balance":float(requester_new)}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as err:
        conn.rollback()
        print(f"Approve Request Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to approve request")
    finally:
        cursor.close()
        conn.close()

@app.post("/api/reverse-transaction")
async def reverse_transaction(req: ReverseRequest):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    try:
        cursor.execute("SELECT * FROM transactions WHERE txn_id = %s LIMIT 1", (req.transaction_id,))
        orig = cursor.fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        sender_id = orig.get('sender_id')
        receiver_id = orig.get('receiver_id')
        if sender_id is None or receiver_id is None:
            raise HTTPException(status_code=400, detail="Transaction is not reversible")
        
        if sender_id != req.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to reverse this transaction")
        
        created = orig.get('created_at')
        if isinstance(created, str):
            parsed = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
                try:
                    parsed = datetime.strptime(created, fmt)
                    break
                except Exception:
                    continue
            if parsed is None:
                try:
                    parsed = datetime.fromisoformat(created)
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid transaction timestamp")
            created = parsed
        
        if not isinstance(created, datetime):
            raise HTTPException(status_code=400, detail="Invalid transaction timestamp")
        
        now = datetime.now()
        delta = (now - created).total_seconds()
        if delta > 30:
            raise HTTPException(status_code=400, detail="Reversal window expired")
        
        amount = float(orig.get('amount', 0))
        
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END),0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END),0) as bal
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (receiver_id, receiver_id, receiver_id, receiver_id))
        bal_res = cursor.fetchone()
        receiver_balance = float(bal_res['bal']) if bal_res and bal_res.get('bal') is not None else 0.0
        if receiver_balance < amount:
            raise HTTPException(status_code=400, detail="Receiver has insufficient funds to reverse")
        
        cursor.execute(
            "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s,%s,%s,%s)",
            (receiver_id, sender_id, amount, f"Reversal of txn {req.transaction_id}")
        )
        
        for wid in (receiver_id, sender_id):
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as balance
                FROM transactions
                WHERE sender_id = %s OR receiver_id = %s
            """, (wid, wid, wid, wid))
            res = cursor.fetchone()
            new_bal = float(res['balance']) if res and res.get('balance') is not None else 0.0
            cursor.execute("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (new_bal, wid))
        
        conn.commit()
        return {"status": "success", "message": "Transaction reversed", "reversal_id": cursor.lastrowid}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as err:
        conn.rollback()
        print(f"Reverse Transaction Error: {err}")
        raise HTTPException(status_code=500, detail="Reversal failed")
    finally:
        cursor.close()
        conn.close()

# Mount static files
if os.path.exists('static'):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting PayFlow Backend on port {port}...")
    print(f"Using database: {SQL_DIALECT}")
    print(f"http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

