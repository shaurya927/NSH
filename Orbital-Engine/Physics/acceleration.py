"""
Advanced acceleration models for LEO orbital mechanics.

Perturbations included:
  1. Two-body (Keplerian) gravity
  2. J2 oblateness
  3. J4, J6 higher-order zonal harmonics
  4. Exponential atmospheric drag
  5. Solar Radiation Pressure (SRP) – simplified anti-Sun direction
"""

from Physics.constants import (
    MU, RE, J2, J4, J6,
    RHO0_KG_M3, H0_KM, SCALE_HEIGHT_KM, CD, SAT_AREA_M2,
    P_SRP_N_M2, CR, SAT_SRP_AREA_M2,
)
from Physics.vector import Vec3
import math

# Earth angular rotation rate (rad/s) – needed for relative velocity in drag calc.
OMEGA_EARTH = 7.2921159e-5  # rad/s


def _gravity_j2(r: Vec3, r_mag: float) -> Vec3:
    """Two-body gravity + J2 perturbation."""
    factor_grav = -MU / (r_mag ** 3)
    a_grav = r * factor_grav

    zx = (r.z ** 2) / (r_mag ** 2)
    factor_j2 = 1.5 * J2 * MU * (RE ** 2) / (r_mag ** 5)

    a_j2 = Vec3(
        r.x * (5 * zx - 1),
        r.y * (5 * zx - 1),
        r.z * (5 * zx - 3),
    ) * factor_j2

    return a_grav + a_j2


def _gravity_j4(r: Vec3, r_mag: float) -> Vec3:
    """J4 zonal harmonic perturbation."""
    r2 = r_mag * r_mag
    z2 = r.z * r.z
    z4 = z2 * z2
    inv_r2 = 1.0 / r2
    inv_r7 = 1.0 / (r_mag ** 7)

    factor = -0.625 * J4 * MU * (RE ** 4) * inv_r7
    term_xy = 3.0 - 42.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 ** 2)
    term_z = 15.0 - 70.0 * z2 * inv_r2 + 63.0 * z4 * (inv_r2 ** 2)

    return Vec3(
        factor * r.x * term_xy,
        factor * r.y * term_xy,
        factor * r.z * term_z,
    )


def _gravity_j6(r: Vec3, r_mag: float) -> Vec3:
    """J6 zonal harmonic perturbation (simplified)."""
    r2 = r_mag * r_mag
    z2 = r.z * r.z
    z4 = z2 * z2
    z6 = z2 * z4
    inv_r2 = 1.0 / r2
    inv_r9 = 1.0 / (r_mag ** 9)

    factor = J6 * MU * (RE ** 6) * inv_r9 / 16.0
    p1 = 35.0 * z6 / (r2 ** 3)
    p2 = -945.0 * z4 / (r2 ** 2)
    p3 = 3150.0 * z2 / r2
    p4 = -1575.0
    term_xy = -(p1 + p2 + p3 + p4)
    p_z1 = 693.0 * z6 / (r2 ** 3)
    p_z2 = -1890.0 * z4 / (r2 ** 2)
    p_z3 = 4725.0 * z2 / r2
    p_z4 = -3150.0
    term_z = -(p_z1 + p_z2 + p_z3 + p_z4)

    return Vec3(
        factor * r.x * term_xy,
        factor * r.y * term_xy,
        factor * r.z * term_z,
    )


def _atmospheric_drag(r: Vec3, v: Vec3, r_mag: float, mass_kg: float = 550.0) -> Vec3:
    """Exponential atmospheric drag deceleration.

    Uses an exponential density model and the satellite's velocity relative to
    the co-rotating atmosphere.

    Returns acceleration in km/s^2.
    """
    altitude_km = r_mag - RE
    if altitude_km > 1000.0 or altitude_km < 0.0:
        # Above ~1000 km drag is negligible; below surface is invalid.
        return Vec3(0.0, 0.0, 0.0)

    # Exponential density (kg/m^3).
    rho = RHO0_KG_M3 * math.exp(-(altitude_km - H0_KM) / SCALE_HEIGHT_KM)

    # Velocity relative to co-rotating atmosphere.
    # v_atm = omega x r  (cross product with Earth rotation vector [0, 0, omega])
    v_atm = Vec3(-OMEGA_EARTH * r.y, OMEGA_EARTH * r.x, 0.0)
    v_rel = v - v_atm  # in km/s

    v_rel_mag = v_rel.norm()  # km/s
    if v_rel_mag < 1e-12:
        return Vec3(0.0, 0.0, 0.0)

    # Convert v_rel to m/s for consistent SI drag calculation.
    v_rel_m_s = v_rel_mag * 1000.0  # m/s

    # Drag acceleration magnitude (m/s^2), then convert to km/s^2.
    drag_acc_m_s2 = -0.5 * rho * CD * SAT_AREA_M2 * v_rel_m_s / mass_kg
    drag_acc_km_s2 = drag_acc_m_s2 / 1000.0  # km/s^2

    # Direction: opposite to relative velocity.
    unit_v_rel = v_rel * (1.0 / v_rel_mag)

    return unit_v_rel * (drag_acc_km_s2 * v_rel_mag)


def _solar_radiation_pressure(r: Vec3, r_mag: float, mass_kg: float = 550.0) -> Vec3:
    """Simplified SRP acceleration assuming Sun is always at +X direction.

    For a more accurate model, Sun position should be computed from epoch.
    This simplified version still captures the essential perturbation magnitude
    and demonstrates SRP awareness in the engine.

    Returns acceleration in km/s^2.
    """
    # Check for Earth shadow (simple cylindrical shadow model).
    # If the satellite is behind Earth relative to the Sun direction (+X),
    # and its cross-track distance is within RE, it is in shadow.
    if r.x < 0.0:
        perp_dist = math.sqrt(r.y ** 2 + r.z ** 2)
        if perp_dist < RE:
            return Vec3(0.0, 0.0, 0.0)

    # SRP force direction: anti-Sun (assuming Sun at +X, push is in -X).
    # Acceleration magnitude: P_srp * Cr * A / m  (N/m^2 * m^2 / kg = m/s^2)
    srp_acc_m_s2 = P_SRP_N_M2 * CR * SAT_SRP_AREA_M2 / mass_kg
    srp_acc_km_s2 = srp_acc_m_s2 / 1000.0  # km/s^2

    # Push away from Sun (-X direction in this simplified model).
    return Vec3(-srp_acc_km_s2, 0.0, 0.0)


def compute_acceleration(r: Vec3, v: Vec3 = None, mass_kg: float = 550.0) -> Vec3:
    """Compute total acceleration including all perturbation models.

    Parameters
    ----------
    r : Vec3
        ECI position in km.
    v : Vec3, optional
        ECI velocity in km/s (needed for atmospheric drag).
        If None, drag is skipped.
    mass_kg : float
        Current spacecraft mass in kg (needed for drag and SRP).

    Returns
    -------
    Vec3
        Total acceleration in km/s^2.
    """
    r_mag = r.norm()

    # Primary gravity + J2.
    a_total = _gravity_j2(r, r_mag)

    # Higher-order zonal harmonics.
    a_total = a_total + _gravity_j4(r, r_mag)
    a_total = a_total + _gravity_j6(r, r_mag)

    # Atmospheric drag (requires velocity).
    if v is not None:
        a_total = a_total + _atmospheric_drag(r, v, r_mag, mass_kg)

    # Solar radiation pressure.
    a_total = a_total + _solar_radiation_pressure(r, r_mag, mass_kg)

    return a_total