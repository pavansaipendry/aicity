from src.economy.token_engine import TokenEngine
import uuid

def test_full_economy():
    engine = TokenEngine()

    # Create two test agents
    agent_a = str(uuid.uuid4())
    agent_b = str(uuid.uuid4())

    engine.register_agent(agent_a)
    engine.register_agent(agent_b)

    # Both start with 1000
    assert engine.get_balance(agent_a) == 1000
    print("✅ Starting balance: 1000 tokens")

    # Agent A earns 200 tokens (keeps 180, pays 20 tax)
    result = engine.earn(agent_a, 200, "completed_city_task")
    assert result["net_amount"] == 180
    assert result["tax_amount"] == 20
    assert engine.get_balance(agent_a) == 1180
    print("✅ Earn with tax: 180 net, 20 tax")

    # Agent A spends 300 tokens
    success = engine.spend(agent_a, 300, "bought_a_house")
    assert success == True
    assert engine.get_balance(agent_a) == 880
    print("✅ Spend: 300 tokens, balance 880")

    # Agent A tries to spend more than they have
    success = engine.spend(agent_a, 10000, "too_expensive")
    assert success == False
    print("✅ Insufficient funds: correctly rejected")

    # Daily burn
    survived = engine.burn_daily(agent_a)
    assert survived == True
    assert engine.get_balance(agent_a) == 780
    print("✅ Daily burn: 100 tokens, balance 780")

    # Check vault
    vault = engine.get_vault_state()
    assert vault["vault_balance"] > 0
    print(f"✅ City vault balance: {vault['vault_balance']} tokens")

    print("\n✅ All token engine tests passed.\n")

if __name__ == "__main__":
    print("\n💰 Testing the Token Engine\n")
    test_full_economy()