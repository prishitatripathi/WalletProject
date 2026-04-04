# PayFlow - Professional Transaction Management System

A modern, secure, and feature-rich transaction ledger system built with FastAPI and MySQL, featuring a responsive web interface.

## 🚀 Features

### Core Functionality
- **User Authentication**: Secure login with password hashing
- **User Registration**: Create new accounts with validation
- **Transaction Management**:
  - Deposits (add money to account)
  - Withdrawals (remove money from account)
  - Transfers (send money between users)
- **Transaction History**: Complete ledger with detailed transaction records
- **Real-time Balance Updates**: Automatic balance calculations and updates

### Professional Features
- **Secure Password Storage**: Uses Werkzeug security for password hashing
- **Input Validation**: Comprehensive validation on all endpoints
- **Error Handling**: Proper error responses and user feedback
- **Responsive Design**: Modern UI that works on all devices
- **Transaction Analytics**: Monthly summaries and statistics
- **Role-based Access**: Support for user and admin roles

### Technical Features
- **RESTful API**: Clean, documented API endpoints
- **Database Transactions**: Atomic operations for data consistency
- **CORS Support**: Cross-origin resource sharing enabled
- **SQL Injection Protection**: Parameterized queries throughout

## 🛠️ Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: MySQL with PyMySQL
- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Security**: Werkzeug password hashing
- **UI Framework**: Custom responsive design with Inter font

## 📁 Project Structure

```
WalletProject/
├── main.py                 # FastAPI backend server
├── index.html             # Frontend application
├── create-db-template.sql # Database schema and sample data
├── __pycache__/           # Python cache files
└── README.md             # This documentation
```

## 🔧 Installation & Setup

### Prerequisites
- Python 3.8+
- MySQL Server
- pip (Python package manager)

### 1. Database Setup
```bash
# Start MySQL service (if not running)
# Create database and tables
mysql -u root -p < create-db-template.sql
```

### 2. Python Dependencies
```bash
pip install fastapi uvicorn pymysql werkzeug
```

### 3. Configuration
Update the database configuration in `main.py`:
```python
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'your_mysql_password',  # Update this
    'database': 'wallet_db'
}
```

## 🚀 Running the Application

### Start the Backend Server
```bash
python main.py
```
The API will be available at `http://127.0.0.1:8080`

### Access the Frontend
Open `index.html` in your web browser or serve it with a web server.

## 📡 API Endpoints

### Authentication
- `POST /api/login` - User login
- `POST /api/register` - User registration

### Transactions
- `POST /api/transaction` - Create new transaction
- `GET /api/ledger/{wallet_id}` - Get transaction history

### Users
- `GET /api/users` - List all users (for admin)

## 🔐 Default Users

The system comes with pre-configured users:
- **admin** / password (Administrator)
- **alice** / password (Regular User)
- **bob** / password (Regular User)

## 🎨 User Interface

### Login/Register
- Clean authentication forms
- Toggle between login and registration
- Real-time validation feedback

### Dashboard
- **Balance Overview**: Current account balance
- **Transaction Statistics**: Monthly transaction count and change
- **Transaction Form**: Create deposits, withdrawals, and transfers
- **Transaction History**: Detailed table of all transactions

### Responsive Design
- Works on desktop, tablet, and mobile
- Modern dark theme with professional styling
- Smooth animations and transitions

## 🔒 Security Features

- **Password Hashing**: All passwords are securely hashed
- **SQL Injection Prevention**: Parameterized queries
- **Input Validation**: All inputs are validated
- **Error Handling**: Sensitive information not exposed in errors
- **CORS Configuration**: Properly configured for web access

## 📊 Database Schema

### Users Table
```sql
- user_id (Primary Key)
- username (Unique)
- password_hash (Hashed password)
- full_name
- role (user/admin)
- created_at
```

### Wallets Table
```sql
- wallet_id (Primary Key)
- user_id (Foreign Key)
- balance (Decimal)
```

### Transactions Table
```sql
- txn_id (Primary Key)
- sender_id (Foreign Key, nullable)
- receiver_id (Foreign Key, nullable)
- amount (Decimal)
- description
- created_at
```

## 🔄 Transaction Types

1. **Deposit**: Money added to account (receiver_id set, sender_id null)
2. **Withdrawal**: Money removed from account (sender_id set, receiver_id null)
3. **Transfer**: Money moved between users (both sender_id and receiver_id set)

## 🚀 Future Enhancements

- JWT token authentication
- Email notifications
- Transaction categories/tags
- Export functionality (PDF/CSV)
- Admin dashboard
- Multi-currency support
- Transaction search and filtering
- Recurring transactions
- Budget tracking

## 📝 Usage Examples

### Creating a Deposit
```javascript
POST /api/transaction
{
  "transaction_type": "deposit",
  "amount": 100.00,
  "description": "Salary deposit"
}
```

### Creating a Transfer
```javascript
POST /api/transaction
{
  "transaction_type": "transfer",
  "amount": 50.00,
  "description": "Lunch payment",
  "receiver_username": "alice"
}
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source and available under the MIT License.

## 🆘 Support

For issues or questions:
1. Check the console for error messages
2. Verify database connection
3. Ensure all dependencies are installed
4. Check network connectivity for API calls

---

**Built with ❤️ for professional transaction management**
