-- The immutable token ledger
-- Every transaction ever made in AIcity lives here
-- NOTHING is ever deleted from this table

CREATE TABLE IF NOT EXISTS token_transactions (
    id          SERIAL PRIMARY KEY,
    timestamp   TIMESTAMPTZ DEFAULT NOW(),
    from_agent  VARCHAR(36),  -- NULL means city vault
    to_agent    VARCHAR(36),  -- NULL means city vault
    amount      INTEGER NOT NULL,
    tax_amount  INTEGER DEFAULT 0,
    reason      VARCHAR(255) NOT NULL,
    tx_type     VARCHAR(50) NOT NULL
    -- tx_type: earn, spend, tax, mint, burn, transfer
);

-- The city vault — tracks total city wealth
CREATE TABLE IF NOT EXISTS city_vault (
    id              SERIAL PRIMARY KEY,
    total_supply    BIGINT NOT NULL DEFAULT 10000000,
    circulating     BIGINT NOT NULL DEFAULT 0,
    vault_balance   BIGINT NOT NULL DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Agent token balances — always in sync with transactions
CREATE TABLE IF NOT EXISTS agent_balances (
    agent_id    VARCHAR(36) PRIMARY KEY,
    balance     INTEGER NOT NULL DEFAULT 1000,
    total_earned    BIGINT DEFAULT 0,
    total_spent     BIGINT DEFAULT 0,
    last_updated    TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize the vault with 10 million tokens
INSERT INTO city_vault (total_supply, circulating, vault_balance)
VALUES (10000000, 0, 10000000)
ON CONFLICT DO NOTHING;