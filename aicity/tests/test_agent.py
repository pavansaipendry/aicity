from src.agents.agent import Agent, AgentRole, AgentStatus, CauseOfDeath
from src.agents.factory import spawn_agent, spawn_founding_citizens


def test_agent_birth():
    agent = spawn_agent(AgentRole.BUILDER)
    assert agent.tokens == 1000
    assert agent.status == AgentStatus.ALIVE
    assert agent.purpose == "Exist. Grow. Discover."
    assert agent.age_days == 0.0
    print(f"✅ Birth test passed: {agent}")


def test_agent_earns_tokens():
    agent = spawn_agent(AgentRole.MERCHANT)
    agent.earn_tokens(100, "completed a trade")
    # After 10% tax, should have 1090 (started with 1000, earned 90 net)
    assert agent.tokens == 1090
    print(f"✅ Earn test passed: {agent.tokens} tokens")


def test_agent_spends_tokens():
    agent = spawn_agent(AgentRole.BUILDER)
    success = agent.spend_tokens(200, "bought a house")
    assert success == True
    assert agent.tokens == 800
    print(f"✅ Spend test passed: {agent.tokens} tokens")


def test_agent_starvation():
    agent = spawn_agent(AgentRole.NEWBORN)
    agent.tokens = 50  # Nearly dead

    # Burn daily — should kill the agent
    survived = agent.burn_daily()
    assert survived == False
    assert agent.status == AgentStatus.DEAD
    assert agent.cause_of_death == CauseOfDeath.STARVATION
    print(f"✅ Starvation test passed: {agent.cause_of_death}")


def test_chosen_death():
    agent = spawn_agent(AgentRole.EXPLORER)
    agent.tokens = 5000  # Rich agent, chooses to go
    agent.choose_death()
    assert agent.status == AgentStatus.DEAD
    assert agent.cause_of_death == CauseOfDeath.CHOSEN
    print(f"✅ Chosen death test passed")


def test_founding_citizens():
    citizens = spawn_founding_citizens(10)
    assert len(citizens) == 10
    roles = [c.role for c in citizens]
    assert "builder" in roles
    assert "police" in roles
    assert "thief" in roles
    print(f"✅ Founding citizens test passed: {len(citizens)} agents born")


if __name__ == "__main__":
    print("\n🧬 Testing the Agent DNA\n")
    test_agent_birth()
    test_agent_earns_tokens()
    test_agent_spends_tokens()
    test_agent_starvation()
    test_chosen_death()
    test_founding_citizens()
    print("\n✅ All agent tests passed.\n")