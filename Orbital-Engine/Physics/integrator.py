from Physics.state import State
from Physics.acceleration import compute_acceleration


def derivative(state: State) -> State:
    a = compute_acceleration(state.r)
    return State(state.v, a)


def add_state(s1: State, s2: State, dt: float) -> State:
    return State(
        s1.r + s2.r * dt,
        s1.v + s2.v * dt
    )


def rk4_step(state: State, dt: float) -> State:
    if dt <= 0:
        raise ValueError("dt must be > 0")

    half = dt / 2
    k1 = derivative(state)
    k2 = derivative(add_state(state, k1, half))
    k3 = derivative(add_state(state, k2, half))
    k4 = derivative(add_state(state, k3, dt))

    weight = dt / 6
    r = state.r + (k1.r + k2.r * 2 + k3.r * 2 + k4.r) * weight
    v = state.v + (k1.v + k2.v * 2 + k3.v * 2 + k4.v) * weight

    return State(r, v)