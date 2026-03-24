# ---------- Earth gravitational constants ----------
MU = 398600.4418          # km^3/s^2  (gravitational parameter)
RE = 6378.137             # km        (equatorial radius)
J2 = 1.08263e-3           # J2 oblateness coefficient
J4 = -1.61098e-6          # J4 zonal harmonic
J6 = 5.40e-7              # J6 zonal harmonic

# ---------- Atmospheric drag (exponential model) ----------
# Reference values at h0 = 400 km altitude (typical LEO).
RHO0_KG_M3 = 2.803e-12   # kg/m^3   reference density at h0
H0_KM = 400.0             # km       reference altitude
SCALE_HEIGHT_KM = 58.515  # km       exponential scale height near 400 km
CD = 2.2                  # drag coefficient (typical for a flat plate)
SAT_AREA_M2 = 10.0        # m^2      cross-sectional area of each satellite

# ---------- Solar Radiation Pressure ----------
P_SRP_N_M2 = 4.56e-6     # N/m^2    solar radiation pressure at 1 AU
CR = 1.2                  # reflectivity coefficient (1=absorb, 2=perfect mirror)
SAT_SRP_AREA_M2 = 10.0   # m^2      effective SRP area (may differ from drag area)

# ---------- Standard gravity ----------
G0_M_S2 = 9.80665        # m/s^2