import os
import sys
import numpy as np
import gymnasium as gym

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gymnasium import spaces

from engine.core import ACMEngine
from engine.utils import EngineConfig


class CollisionAvoidanceEnv(gym.Env):
    """
    Reinforcement Learning environment for Autonomous Collision Avoidance.
    
    Goal: Given an incoming piece of debris, calculate the exact (dv_r, dv_t, dv_n)
    maneuver vector to safely evade the debris while minimizing fuel consumption
    and station-keeping deviation.
    """
    metadata = {"render_modes": ["ansi"]}

    def __init__(self, tca_horizon_s: float = 600.0, step_dt_s: float = 10.0):
        super().__init__()
        
        self.tca_horizon_s = tca_horizon_s
        self.step_dt_s = step_dt_s
        self.engine = None
        self.sat_id = "SAT-AI-01"
        self.deb_id = "DEB-KILLER"

        # Observation Space:
        # [rel_x, rel_y, rel_z, rel_vx, rel_vy, rel_vz, sat_fuel_kg, station_keeping_deviation_km]
        # Bounded between very large +/- values since relative distances in km can be large.
        high_obs = np.array([
            1e5, 1e5, 1e5,      # relative positions (km)
            20.0, 20.0, 20.0,   # relative velocities (km/s)
            100.0,              # fuel kg
            1e5                 # deviation km
        ], dtype=np.float32)
        self.observation_space = spaces.Box(low=-high_obs, high=high_obs, dtype=np.float32)

        # Action Space: (Continuous thrust in RTN frame)
        # [dv_r, dv_t, dv_n] bounded between -15.0 m/s and +15.0 m/s
        self.max_dv_m_s = 15.0
        self.action_space = spaces.Box(
            low=np.array([-self.max_dv_m_s, -self.max_dv_m_s, -self.max_dv_m_s]),
            high=np.array([self.max_dv_m_s, self.max_dv_m_s, self.max_dv_m_s]),
            dtype=np.float32
        )

        self._min_distance = float('inf')
        self._initial_fuel = 50.0

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # Initialize the high-performance physics engine with ML tolerances
        cfg = EngineConfig(
            integration_tick_s=self.step_dt_s,
            enable_auto_avoidance=False,   # ML agent handles avoidance
            enable_station_keeping=False,  # ML agent handles recovery
            collision_distance_km=0.100    # 100 meters
        )
        self.engine = ACMEngine(cfg)

        # Generate a random but perilous scenario where debris is on a collision course
        # We place them at the exact same location at t=TCA, then propagate backward
        r_collision = np.array([6778.0, 0.0, 0.0], dtype=np.float64) # 400km altitude
        v_sat = np.array([0.0, 7.66, 0.0], dtype=np.float64)
        
        # Debris approach vector (randomized a bit to force agent to learn generalized policy)
        approach_angle = self.np_random.uniform(-np.pi/4, np.pi/4)
        v_deb = np.array([
            np.sin(approach_angle) * 7.5,
            np.cos(approach_angle) * 7.5,
            self.np_random.uniform(-0.1, 0.1)
        ], dtype=np.float64)

        # Simplistic backward projection for starting state (ignores gravity curvature for approx start)
        r_sat_start = r_collision - v_sat * self.tca_horizon_s
        r_deb_start = r_collision - v_deb * self.tca_horizon_s
        
        # Add a tiny noise to miss distance so they don't exactly pass through each other
        r_deb_start += self.np_random.uniform(-0.05, 0.05, size=3)

        self._initial_fuel = 50.0
        
        # Ingest state into engine
        telemetry = {
            "objects": [
                {
                    "id": self.sat_id, "type": "SATELLITE",
                    "r_km": r_sat_start.tolist(), "v_km_s": v_sat.tolist(),
                    "mass_kg": 550.0, "fuel_kg": self._initial_fuel
                },
                {
                    "id": self.deb_id, "type": "DEBRIS",
                    "r_km": r_deb_start.tolist(), "v_km_s": v_deb.tolist(),
                    "mass_kg": 100.0
                }
            ]
        }
        self.engine.ingest_telemetry(telemetry)
        
        self.elapsed_s = 0.0
        self._min_distance = float('inf')
        
        return self._get_obs(), {}

    def step(self, action):
        # Action is exactly one burn decision per episode (at TCA - horizon)
        # We apply the action, then simulate forward until horizon to see the result.
        
        dv_rtn = np.clip(action, self.action_space.low, self.action_space.high)
        # Convert m/s -> km/s for the engine API
        dv_rtn_km_s = dv_rtn / 1000.0

        # Schedule the maneuver immediately.
        try:
            self.engine._scheduler.schedule_immediate(
                object_id=self.sat_id,
                epoch_s=self.engine.current_time_s,
                delta_v_rtn_km_s=dv_rtn_km_s
            )
        except ValueError as e:
            # If gym check_env steps multiple times without a reset, handle the cooldown violation gracefully.
            pass

        # Fast-forward simulation until post-TCA
        min_distance = float('inf')
        collision_occurred = False
        
        steps = int((self.tca_horizon_s + 100) / self.step_dt_s)
        for _ in range(steps):
            res = self.engine.step_simulation(self.step_dt_s)
            
            # Track closest approach over the simulation window
            r_sat, _, _ = self.engine._state_by_id(self.sat_id)
            r_deb, _, _ = self.engine._state_by_id(self.deb_id)
            dist = np.linalg.norm(r_sat - r_deb)
            min_distance = min(min_distance, dist)
            
            if dist < 0.100:  # < 100m indicates critical collision
                collision_occurred = True

        self._min_distance = min_distance

        # Fetch final states to compute rewards
        sk_reports = {sk["id"]: sk for sk in self.engine._build_station_keeping_report()}
        sk_info = sk_reports.get(self.sat_id, {})
        sk_dev_km = sk_info.get("deviation_km", 0.0)
        
        idx = self.engine.id_to_index[self.sat_id][1]
        final_fuel = float(self.engine._sat.fuel[idx])
        fuel_used = self._initial_fuel - final_fuel

        # ── Reinforcement Learning Reward Function Schema ──
        reward = 0.0
        
        if collision_occurred:
            reward -= 10000.0  # Mission failure (Kessler Syndrome triggered)
        else:
            reward += 100.0    # Successfully evaded debris
            
            # Heavily penalize huge maneuvers that waste fuel when a small one would do
            reward -= (fuel_used * 50.0)
            
            # Penalize huge station-keeping drift
            reward -= (sk_dev_km * 2.0)

            # Bonus for keeping miss distance safe but not excessively large
            if min_distance > 1.0:
                reward += 10.0

        terminated = True  # Episode is one maneuver sequence prediction
        truncated = False
        
        info = {
            "min_miss_distance_km": self._min_distance,
            "fuel_consumed_kg": fuel_used,
            "station_keeping_dev_km": sk_dev_km,
            "collision": collision_occurred
        }
        
        return self._get_obs(), float(reward), terminated, truncated, info

    def _get_obs(self):
        r_sat, v_sat, _ = self.engine._state_by_id(self.sat_id)
        r_deb, v_deb, _ = self.engine._state_by_id(self.deb_id)
        
        rel_pos = r_deb - r_sat
        rel_vel = v_deb - v_sat
        
        idx = self.engine.id_to_index[self.sat_id][1]
        fuel = float(self.engine._sat.fuel[idx])
        sk_dev = float(self.engine._sk_last_deviation_km.get(self.sat_id, 0.0))
        
        return np.concatenate([
            rel_pos, rel_vel, [fuel, sk_dev]
        ]).astype(np.float32)

# Important hack for ML training mode: 
# Patch the scheduler so it accepts `schedule_immediate` to bypass comm-latency and cooldown bounds
from engine.scheduler import ManeuverScheduler, ScheduledManeuver
import heapq

def schedule_immediate(self, object_id, epoch_s, delta_v_rtn_km_s):
    maneuver = ScheduledManeuver(
        object_id=object_id,
        epoch_s=epoch_s,
        delta_v_rtn_km_s=delta_v_rtn_km_s,
        requires_los=False
    )
    # Bypass cooldown checks entirely for RL episodes 
    self._seq += 1
    heapq.heappush(self._heap, (float(epoch_s), self._seq, maneuver))
    self._last_epoch_by_object[object_id] = float(epoch_s)
    
ManeuverScheduler.schedule_immediate = schedule_immediate
