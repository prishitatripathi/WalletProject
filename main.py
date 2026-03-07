from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import pymysql
import pymysql.cursors
import uvicorn
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from typing import Optional
from fastapi import Query
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '1704', # Ensure this matches your MySQL root password
    'database': 'wallet_db'
}

# initialize additional tables if they don't exist

def init_db():
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
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
            ) ENGINE=InnoDB;
        """)
        conn.commit()
    except Exception as e:
        print(f"DB init error: {e}")
    finally:
        if conn:
            conn.close()

# call init on startup
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
    transaction_type: str  # 'deposit', 'withdraw', 'transfer', 'request_money'

class ApproveRequest(BaseModel):
    request_id: int
    user_id: int  # the payee approving the request


class ReverseRequest(BaseModel):
    transaction_id: int
    user_id: int  # the wallet_id of the user requesting reversal (must be sender)

@app.post("/api/login")
async def login(req: LoginRequest):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # Get user with password hash
        cursor.execute("""
            SELECT u.user_id, u.username, u.full_name, u.role, u.password_hash, w.wallet_id
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            WHERE u.username = %s
        """, (req.username,))

        user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], req.password):
            # Get calculated balance
            cursor.execute("""
                SELECT COALESCE(SUM(CASE WHEN t.receiver_id = w.wallet_id THEN t.amount ELSE 0 END), 0) -
                       COALESCE(SUM(CASE WHEN t.sender_id = w.wallet_id THEN t.amount ELSE 0 END), 0) as balance
                FROM wallets w
                LEFT JOIN transactions t ON t.sender_id = w.wallet_id OR t.receiver_id = w.wallet_id
                WHERE w.wallet_id = %s
                GROUP BY w.wallet_id
            """, (user['wallet_id'],))
            
            balance_result = cursor.fetchone()
            balance = float(balance_result['balance']) if balance_result else 0.0

            # Update stored balance
            cursor.execute("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (balance, user['wallet_id']))
            conn.commit()

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
    finally:
        if conn:
            conn.close()

@app.post("/api/register")
async def register(req: RegisterRequest):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # Check if username already exists
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (req.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Hash password
        password_hash = generate_password_hash(req.password)

        # Insert user
        cursor.execute(
            "INSERT INTO users (username, password_hash, full_name) VALUES (%s, %s, %s)",
            (req.username, password_hash, req.full_name)
        )
        user_id = cursor.lastrowid

        # Create wallet
        cursor.execute("INSERT INTO wallets (user_id) VALUES (%s)", (user_id,))

        conn.commit()
        return {"status": "success", "message": "User registered successfully"}

    except HTTPException:
        raise
    except Exception as err:
        print(f"Registration Error: {err}")
        raise HTTPException(status_code=500, detail="Registration failed")
    finally:
        if conn:
            conn.close()

@app.post("/api/transaction")
async def create_transaction(req: TransactionRequest):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # Get user's wallet
        cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (req.user_id,))
        wallet = cursor.fetchone()
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")

        wallet_id = wallet['wallet_id']
        receiver_wallet_id = None  # Track receiver for transfers

        # Get current balance from transaction history (ignore pending requests)
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as current_balance
            FROM transactions
            WHERE (sender_id = %s OR receiver_id = %s)
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        
        balance_result = cursor.fetchone()
        current_balance = float(balance_result['current_balance']) if balance_result else 0.0

        if req.transaction_type == 'deposit':
            # Deposit: insert transaction with receiver
            cursor.execute(
                "INSERT INTO transactions (receiver_id, amount, description) VALUES (%s, %s, %s)",
                (wallet_id, req.amount, req.description)
            )

        elif req.transaction_type == 'withdraw':
            # Withdraw: check balance first
            if current_balance < req.amount:
                raise HTTPException(status_code=400, detail="Insufficient funds")
            # Insert transaction with sender
            cursor.execute(
                "INSERT INTO transactions (sender_id, amount, description) VALUES (%s, %s, %s)",
                (wallet_id, req.amount, req.description)
            )

        elif req.transaction_type == 'transfer':
            # Transfer: need receiver
            if not req.receiver_username:
                raise HTTPException(status_code=400, detail="Receiver username required for transfer")

            # Get receiver's wallet
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
            
            # Create transaction record
            cursor.execute(
                "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s, %s, %s, %s)",
                (wallet_id, receiver_wallet_id, req.amount, req.description)
            )
            txn_id = cursor.lastrowid

        elif req.transaction_type == 'request_money':
            # Request Money: insert into money_requests table instead of transactions
            if not req.receiver_username:
                raise HTTPException(status_code=400, detail="Receiver username required for request")

            # Get receiver's wallet (payee)
            cursor.execute("""
                SELECT w.wallet_id FROM wallets w
                JOIN users u ON w.user_id = u.user_id
                WHERE u.username = %s
            """, (req.receiver_username,))
            payee_wallet = cursor.fetchone()
            if not payee_wallet:
                raise HTTPException(status_code=404, detail="User not found")

            payee_wallet_id = payee_wallet['wallet_id']

            # create request record
            cursor.execute(
                "INSERT INTO money_requests (requester_id, payee_id, amount, description, status) VALUES (%s, %s, %s, %s, 'pending')",
                (wallet_id, payee_wallet_id, req.amount, req.description)
            )

        else:
            raise HTTPException(status_code=400, detail="Invalid transaction type")

        conn.commit()
        
        # Get updated balance for sender/user
        cursor.execute("""
            SELECT COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as new_balance
            FROM transactions 
            WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        result = cursor.fetchone()
        new_balance = float(result['new_balance']) if result else 0.0
        
        # Update stored balance for the user
        cursor.execute("UPDATE wallets SET balance = %s WHERE wallet_id = %s", (new_balance, wallet_id))
        
        # If this was a transfer, also update receiver's balance
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
        raise
    except Exception as err:
        print(f"Transaction Error: {err}")
        raise HTTPException(status_code=500, detail="Transaction failed")
    finally:
        if conn:
            conn.close()

@app.get("/api/ledger/{wallet_id}")
async def get_ledger(wallet_id: int):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
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
        cursor.execute(query, (wallet_id, wallet_id))
        transactions = cursor.fetchall()
        return {"transactions": transactions}
    except Exception as err:
        print(f"Ledger Error: {err}")
        return {"transactions": []}
    finally:
        if conn:
            conn.close()

@app.get("/api/user/{user_id}")
async def get_user_data(user_id: int):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # Get user info with calculated balance
        cursor.execute("""
            SELECT u.user_id, u.username, u.full_name, u.role, w.wallet_id,
                   COALESCE(SUM(CASE WHEN t.receiver_id = w.wallet_id THEN t.amount ELSE 0 END), 0) -
                   COALESCE(SUM(CASE WHEN t.sender_id = w.wallet_id THEN t.amount ELSE 0 END), 0) as balance
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            LEFT JOIN transactions t ON t.sender_id = w.wallet_id OR t.receiver_id = w.wallet_id
            WHERE u.user_id = %s
            GROUP BY u.user_id, w.wallet_id
        """, (user_id,))
        user = cursor.fetchone()

        if user:
            # Update the stored balance to match calculated balance
            cursor.execute("UPDATE wallets SET balance = %s WHERE user_id = %s", (user['balance'], user_id))
            conn.commit()
            return {"status": "success", "balance": float(user['balance'])}

        raise HTTPException(status_code=404, detail="User not found")

    except Exception as err:
        print(f"User Data Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to get user data")
    finally:
        if conn:
            conn.close()

@app.get("/api/users/search")
async def search_users(query: str):
    """Search for users by username or name"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        
        search_term = f"%{query}%"
        cursor.execute("""
            SELECT user_id, username, full_name FROM users 
            WHERE (username LIKE %s OR full_name LIKE %s) AND user_id != 0
            LIMIT 10
        """, (search_term, search_term))
        
        users = cursor.fetchall()
        return {"status": "success", "users": users}
    
    except Exception as err:
        print(f"Search Error: {err}")
        return {"status": "error", "users": []}
    finally:
        if conn:
            conn.close()


@app.get("/api/admin/accounts")
async def admin_list_accounts(user_id: int):
    """Return all user accounts and wallet balances for admin users only."""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # Verify requester is admin
        cursor.execute("SELECT role FROM users WHERE user_id = %s", (user_id,))
        r = cursor.fetchone()
        if not r or r.get('role') != 'admin':
            raise HTTPException(status_code=403, detail="Admin access required")

        cursor.execute("""
            SELECT u.user_id, u.username, u.full_name, u.role, w.wallet_id, w.balance
            FROM users u
            JOIN wallets w ON u.user_id = w.user_id
            ORDER BY u.user_id ASC
        """)
        rows = cursor.fetchall()

        accounts = [
            {
                'user_id': row['user_id'],
                'username': row['username'],
                'full_name': row['full_name'],
                'role': row['role'],
                'wallet_id': row['wallet_id'],
                'balance': float(row['balance']) if row['balance'] is not None else 0.0
            }
            for row in rows
        ]

        return {'status': 'success', 'accounts': accounts}

    except HTTPException:
        raise
    except Exception as err:
        print(f"Admin accounts error: {err}")
        raise HTTPException(status_code=500, detail="Failed to fetch accounts")
    finally:
        if conn:
            conn.close()

@app.get("/api/stats")
async def get_stats(user_id: int):
    """Get user statistics"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        
        # Get wallet
        cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (user_id,))
        wallet = cursor.fetchone()
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        wallet_id = wallet['wallet_id']
        
        # Count transactions
        cursor.execute("SELECT COUNT(*) as count FROM transactions WHERE sender_id = %s OR receiver_id = %s", 
                      (wallet_id, wallet_id))
        txn_count = cursor.fetchone()['count']
        
        # Sum received vs sent
        cursor.execute("""
            SELECT 
                COALESCE(SUM(CASE WHEN receiver_id = %s THEN amount ELSE 0 END), 0) as total_received,
                COALESCE(SUM(CASE WHEN sender_id = %s THEN amount ELSE 0 END), 0) as total_sent
            FROM transactions
            WHERE sender_id = %s OR receiver_id = %s
        """, (wallet_id, wallet_id, wallet_id, wallet_id))
        
        result = cursor.fetchone()
        
        return {
            "status": "success",
            "total_transactions": txn_count,
            "total_received": float(result['total_received']),
            "total_sent": float(result['total_sent']),
            "net": float(result['total_received']) - float(result['total_sent'])
        }
    
    except Exception as err:
        print(f"Stats Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to get stats")
    finally:
        if conn:
            conn.close()

@app.get("/api/pending-requests/{wallet_id}")
async def get_pending_requests(wallet_id: int):
    """Get pending money requests where the given wallet is the payee"""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        
        cursor.execute("""
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
        
        reqs = cursor.fetchall()
        
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
    finally:
        if conn:
            conn.close()


@app.get("/api/transactions")
async def list_transactions(
    user_id: int,
    q: Optional[str] = Query(None, description="Search text for description or counterparty"),
    txn_type: Optional[str] = Query(None, description="filter by 'credit' or 'debit'"),
    since: Optional[str] = Query(None, description="ISO date start"),
    until: Optional[str] = Query(None, description="ISO date end"),
    limit: int = 50
):
    """List and filter transactions for a user's wallet."""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # build base query
        sql = """
            SELECT t.*, su.full_name as sender_name, ru.full_name as receiver_name
            FROM transactions t
            LEFT JOIN wallets sw ON t.sender_id = sw.wallet_id
            LEFT JOIN users su ON sw.user_id = su.user_id
            LEFT JOIN wallets rw ON t.receiver_id = rw.wallet_id
            LEFT JOIN users ru ON rw.user_id = ru.user_id
            WHERE (t.sender_id = %s OR t.receiver_id = %s)
        """
        params = [user_id, user_id]

        if q:
            sql += " AND (t.description LIKE %s OR su.username LIKE %s OR ru.username LIKE %s)"
            like = f"%{q}%"
            params.extend([like, like, like])

        if txn_type:
            if txn_type == 'debit':
                sql += " AND t.sender_id = %s"
                params.append(user_id)
            elif txn_type == 'credit':
                sql += " AND t.receiver_id = %s"
                params.append(user_id)

        if since:
            sql += " AND t.created_at >= %s"
            params.append(since)
        if until:
            sql += " AND t.created_at <= %s"
            params.append(until)

        sql += " ORDER BY t.created_at DESC LIMIT %s"
        params.append(limit)

        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
        return {"status": "success", "transactions": rows}

    except Exception as err:
        print(f"Transactions list error: {err}")
        raise HTTPException(status_code=500, detail="Failed to list transactions")
    finally:
        if conn:
            conn.close()


@app.get("/api/contacts")
async def recent_contacts(user_id: int, limit: int = 10):
    """Return recent contacts (counterparties) for a user's wallet."""
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        # find wallet
        cursor.execute("SELECT wallet_id FROM wallets WHERE user_id = %s", (user_id,))
        w = cursor.fetchone()
        if not w:
            raise HTTPException(status_code=404, detail="Wallet not found")
        wid = w['wallet_id']

        cursor.execute("""
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

        rows = cursor.fetchall()
        return {"status": "success", "contacts": rows}

    except HTTPException:
        raise
    except Exception as err:
        print(f"Contacts error: {err}")
        return {"status": "error", "contacts": []}
    finally:
        if conn:
            conn.close()

@app.post("/api/approve-request")
async def approve_request(req: ApproveRequest):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # fetch money request
        cursor.execute("SELECT * FROM money_requests WHERE request_id = %s", (req.request_id,))
        request_row = cursor.fetchone()
        if not request_row:
            raise HTTPException(status_code=404, detail="Request not found")
        if request_row['status'] != 'pending':
            raise HTTPException(status_code=400, detail="Request already processed")

        # ensure payee matches
        if request_row['payee_id'] != req.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to approve this request")

        # check payee balance
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

        # perform transfer from payee -> requester
        cursor.execute(
            "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s,%s,%s,%s)",
            (request_row['payee_id'], request_row['requester_id'], amount, request_row['description'])
        )

        # mark request approved
        cursor.execute("UPDATE money_requests SET status='approved' WHERE request_id=%s", (req.request_id,))
        conn.commit()

        # compute new balances for both parties
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
        raise
    except Exception as err:
        print(f"Approve Request Error: {err}")
        raise HTTPException(status_code=500, detail="Failed to approve request")
    finally:
        if conn:
            conn.close()


@app.post("/api/reverse-transaction")
async def reverse_transaction(req: ReverseRequest):
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()

        # fetch the original transaction (use txn_id column)
        cursor.execute("SELECT * FROM transactions WHERE txn_id = %s LIMIT 1", (req.transaction_id,))
        orig = cursor.fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="Transaction not found")

        # ensure sender and receiver exist on the transaction
        sender_id = orig.get('sender_id')
        receiver_id = orig.get('receiver_id')
        if sender_id is None or receiver_id is None:
            raise HTTPException(status_code=400, detail="Transaction is not reversible")

        # only the original sender may request reversal
        if sender_id != req.user_id:
            raise HTTPException(status_code=403, detail="Not authorized to reverse this transaction")

        # parse created_at robustly without extra dependencies
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

        # allow reversal only within a short window (30 seconds)
        now = datetime.now()
        delta = (now - created).total_seconds()
        if delta > 30:
            raise HTTPException(status_code=400, detail="Reversal window expired")

        amount = float(orig.get('amount', 0))

        # check current balance of the original receiver (they must still have the funds)
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

        # insert reversal transaction (receiver -> sender)
        cursor.execute(
            "INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES (%s,%s,%s,%s)",
            (receiver_id, sender_id, amount, f"Reversal of txn {req.transaction_id}")
        )

        # update stored balances for both wallets
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
        raise
    except Exception as err:
        print(f"Reverse Transaction Error: {err}")
        raise HTTPException(status_code=500, detail="Reversal failed")
    finally:
        if conn:
            conn.close()

# Mount static files to serve index.html and other assets
if os.path.exists('static'):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html on root path
@app.get("/")
async def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    print("Starting PayFlow Backend on port 8080...")
    print("✨ Modern Fintech Wallet API")
    print("http://localhost:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)