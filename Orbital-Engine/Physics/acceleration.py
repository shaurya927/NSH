from Physics.constants import MU, RE, J2
from Physics.vector import Vec3
import math

def compute_acceleration(r: Vec3) -> Vec3:
    r_mag = r.norm()

    # Gravity
    factor_grav = -MU / (r_mag**3)
    a_grav = r * factor_grav

    # J2 perturbation
    zx = (r.z**2) / (r_mag**2)
    factor_j2 = 1.5 * J2 * MU * (RE**2) / (r_mag**5)

    a_j2 = Vec3(
        r.x * (5*zx - 1),
        r.y * (5*zx - 1),
        r.z * (5*zx - 3)
    ) * factor_j2

    return a_grav + a_j2