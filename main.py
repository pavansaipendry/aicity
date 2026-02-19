from src.os.city import AICity

if __name__ == "__main__":
    # Create the city
    city = AICity()

    # The Big Bang — first 10 agents are born
    city.big_bang(agent_count=10)

    # Run for 30 simulated days
    # speed=0.3 means 0.3 seconds per day — fast enough to watch, slow enough to read
    city.run(days=30, speed=0.3)

