import requests
import numpy as np
import logging
from datetime import datetime, timezone
from sgp4.api import Satrec, WGS84

logger = logging.getLogger("TLE_INGESTOR")
logging.basicConfig(level=logging.INFO)

class TLEIngestor:
    """Fetches real-world satellite TLEs from CelesTrak and converts to Cartesian vectors."""
    
    CELESTRAK_URLS = {
        "starlink": "https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle",
        "active": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle",
        "stations": "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"
    }

    def __init__(self):
        self.satellites = []

    def fetch_constellation(self, category: str = "starlink", max_count: int = 100):
        url = self.CELESTRAK_URLS.get(category)
        if not url:
            raise ValueError(f"Unknown category. Choose from {list(self.CELESTRAK_URLS.keys())}")
            
        logger.info(f"Fetching real TLE data for {category}...")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            lines = response.text.strip().split('\n')
            
            self.satellites = []
            
            # TLEs come in 3-line groups (Title, Line 1, Line 2)
            parsed_count = 0
            for i in range(0, len(lines), 3):
                if i + 2 >= len(lines) or parsed_count >= max_count:
                    break
                    
                name = lines[i].strip()
                line1 = lines[i+1].strip()
                line2 = lines[i+2].strip()
                
                try:
                    sat = Satrec.twoline2rv(line1, line2)
                    self.satellites.append({
                        "name": name,
                        "satrec": sat
                    })
                    parsed_count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse TLE for {name}: {e}")
                    
            logger.info(f"Successfully loaded {len(self.satellites)} real-world objects.")
            return self.satellites
            
        except Exception as e:
            logger.error(f"Failed to fetch TLEs: {e}")
            return []
            
    def get_cartesian_states(self, target_time_utc: datetime = None):
        """Calculates exact (x,y,z) and (vx,vy,vz) for all fetched satellites at a given time."""
        if not target_time_utc:
            target_time_utc = datetime.now(timezone.utc)
            
        # SGP4 takes Julian Date
        jd, fr = self._jday_from_datetime(target_time_utc)
        
        results = []
        for sat_data in self.satellites:
            sat = sat_data["satrec"]
            e, r, v = sat.sgp4(jd, fr)
            
            if e != 0:
                logger.debug(f"SGP4 Propagator error {e} for {sat_data['name']}")
                continue
                
            # CelesTrak output is in TEME (True Equator Mean Equinox). 
            # For hackathon visualization, TEME is visually identical to J2000/ECI.
            results.append({
                "name": sat_data["name"],
                "r": np.array(r), # km
                "v": np.array(v)  # km/s
            })
            
        return results
        
    @staticmethod
    def _jday_from_datetime(dt):
        """Converts datetime to Julian date components required by python-sgp4."""
        # Derived from standard Julian Date math
        year = dt.year
        month = dt.month
        day = dt.day
        hour = dt.hour
        minute = dt.minute
        second = dt.second + dt.microsecond / 1000000.0
        
        if month <= 2:
            year -= 1
            month += 12
        
        A = year // 100
        B = 2 - A + A // 4
        
        jd = int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5
        fr = (hour + minute / 60.0 + second / 3600.0) / 24.0
        
        return jd, fr

if __name__ == "__main__":
    # Test execution
    ingestor = TLEIngestor()
    ingestor.fetch_constellation("stations", max_count=5) # Load ISS + some others
    states = ingestor.get_cartesian_states()
    for s in states:
        print(f"{s['name']}: {s['r']} km | {np.linalg.norm(s['v']):.2f} km/s")
