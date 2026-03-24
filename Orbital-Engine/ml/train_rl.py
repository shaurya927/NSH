import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stable_baselines3 import PPO
from stable_baselines3.common.env_checker import check_env
from cola_env import CollisionAvoidanceEnv


def train_agent(timesteps=50_000, save_path="models/ppo_cola_v1"):
    print("=" * 60)
    print("🚀 Initializing Project AETHER AI Evasion Model (PPO)")
    print("=" * 60)

    # 1. Initialize custom RL Environment bridging ACMEngine physics
    env = CollisionAvoidanceEnv(tca_horizon_s=600.0, step_dt_s=10.0)
    
    # 2. Validate Gymnasium compliance
    print("\nValidating Gymnasium API compliance...")
    check_env(env, warn=True)
    print("Environment checks passed! Proceeding to training.\n")

    # 3. Model construction
    # We use Proximal Policy Optimization (PPO), ideal for continuous RTN thrust control
    model = PPO(
        "MlpPolicy", 
        env, 
        verbose=1,
        learning_rate=0.0003,
        n_steps=1024,
        batch_size=64,
        ent_coef=0.01
    )

    print(f"\n🧠 Commencing Training for {timesteps} timesteps...")
    start = time.time()
    
    # 4. Agent Learning
    # During this process, the ML agent repeatedly simulates collision scenarios
    # against the physical constants of the hackathon rules and learns to use
    # minimal fuel to evade the Kessler debris.
    try:
        model.learn(total_timesteps=timesteps, progress_bar=True)
    except KeyboardInterrupt:
        print("\n\n⚠️ Training interrupted by user. Saving checkpoint...")

    # 5. Save the trained weights
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    model.save(save_path)
    print(f"\n✅ Training Complete! Model saved to {save_path}.zip")
    print(f"Elapsed time: {time.time() - start:.2f} seconds.")


def evaluate_agent(load_path="models/ppo_cola_v1"):
    print("\n🔍 Evaluating Trained AI Agent...")
    env = CollisionAvoidanceEnv(tca_horizon_s=600.0, step_dt_s=10.0)
    
    try:
        model = PPO.load(load_path, env=env)
    except FileNotFoundError:
        print("Model file not found. Ensure you run train_agent() first.")
        return

    obs, _ = env.reset()
    
    # The agent predicts the optimal (dv_r, dv_t, dv_n) evasion maneuver
    action, _states = model.predict(obs, deterministic=True)
    
    print(f"Incoming Debris Rel State: Pos={obs[0:3]} | Vel={obs[3:6]}")
    print(f"🤖 AI Recommended RTN Maneuver (m/s): ")
    print(f"   Radial (R):     {action[0]:.4f} m/s")
    print(f"   Transverse (T): {action[1]:.4f} m/s")
    print(f"   Normal (N):     {action[2]:.4f} m/s")

    # Simulate outcome
    obs, reward, done, truncated, info = env.step(action)
    
    print("\n--- Mission Outcome ---")
    print(f"Collision Critical: {info['collision']}")
    print(f"Min Miss Distance:  {info['min_miss_distance_km']:.4f} km")
    print(f"Fuel Consumed:      {info['fuel_consumed_kg']:.4f} kg")
    print(f"Station Drift:      {info['station_keeping_dev_km']:.4f} km")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AETHER AI Maneuver Training")
    parser.add_argument("--eval", action="store_true", help="Evaluate existing model instead of training")
    parser.add_argument("--timesteps", type=int, default=10000, help="Number of timesteps to train")
    
    args = parser.parse_args()
    
    if args.eval:
        evaluate_agent()
    else:
        train_agent(timesteps=args.timesteps)
