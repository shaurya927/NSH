"""
RK4 integrator for single-object state propagation.

Now passes velocity to the acceleration function so that velocity-dependent
perturbations (atmospheric drag) are properly evaluated at every RK4 stage.
"""

from Physics.state import State
from Physics.acceleration import compute_acceleration


def derivative(state: State, mass_kg: float = 550.0) -> State:
    a = compute_acceleration(state.r, v=state.v, mass_kg=mass_kg)
    return State(state.v, a)


def add_state(s1: State, s2: State, dt: float) -> State:
    return State(
        s1.r + s2.r * dt,
        s1.v + s2.v * dt
    )


def rk4_step(state: State, dt: float, mass_kg: float = 550.0) -> State:
    """Fourth-order Runge-Kutta integrator for a single object.

    Parameters
    ----------
    state : State
        Current ECI state (r in km, v in km/s).
    dt : float
        Time step in seconds.
    mass_kg : float
        Current spacecraft mass in kg (used for drag/SRP).

    Returns
    -------
    State
        Propagated state after dt seconds.
    """
    if dt <= 0:
        raise ValueError("dt must be > 0")

    half = dt / 2
    k1 = derivative(state, mass_kg)
    k2 = derivative(add_state(state, k1, half), mass_kg)
    k3 = derivative(add_state(state, k2, half), mass_kg)
    k4 = derivative(add_state(state, k3, dt), mass_kg)

    weight = dt / 6
    r = state.r + (k1.r + k2.r * 2 + k3.r * 2 + k4.r) * weight
    v = state.v + (k1.v + k2.v * 2 + k3.v * 2 + k4.v) * weight

    return State(r, v)