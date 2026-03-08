-- PostgreSQL version of the database schema
-- Run this in your Render PostgreSQL database

-- Create tables
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS wallets (
    wallet_id SERIAL PRIMARY KEY,
    user_id INT NOT NULL UNIQUE,
    balance DECIMAL(18, 2) DEFAULT 0.00,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id SERIAL PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    amount DECIMAL(18, 2) NOT NULL,
    description VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_id);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_wallets_user ON wallets(user_id);

-- Insert test users (password is 'password' for all)
INSERT INTO users (username, password_hash, full_name, role) VALUES
('admin', 'scrypt:32768:8:1$Puvu9dNAVykAMjIF$fee2f9ac1631d868c7193a998f08bd9042acf0cc24698c70c036c9c0690eb4facd063320b6350fd266dedeb137f3560a37e2a40a51bfa889908eb336b1d78a22', 'System Administrator', 'admin'),
('alice', 'scrypt:32768:8:1$1gQkpUSAOZyeAIcJ$592ccd58b3ad509df913b01d3b84afe08cdca575f74a534c6aae16b300c21721de2b638221b2184b7ddfc475b24d57d9b5bd8f34d010202a2fa23e32a5135c92', 'Alice Vance', 'user'),
('bob', 'scrypt:32768:8:1$KVFwOTGHgeNbHlkG$cab71bb6d2ce51f97df5b062ce08f1fe64640773a5455e9dc844d95ed151ef510e4c0762dcbbb3a9fa8764de9ec6479c79f9919c08550e82dec7c90203b4e21c', 'Robert Fox', 'user')
ON CONFLICT (username) DO NOTHING;

INSERT INTO wallets (user_id, balance) VALUES
(1, 500000.00), (2, 2500.50), (3, 120.00)
ON CONFLICT (user_id) DO NOTHING;

INSERT INTO transactions (sender_id, receiver_id, amount, description) VALUES
(1, 2, 500.00, 'Welcome Bonus'),
(2, 3, 50.00, 'Lunch split');

