import httpx
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger("AETHER_INTEGRATIONS")
logging.basicConfig(level=logging.INFO)

class SpaceWeatherMonitor:
    """Uses real-world NOAA SWPC APIs to pull live geomagnetics / solar flux."""
    
    API_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
    
    def __init__(self):
        self.current_kp = 2.0
        self.storm_active = False
        
    async def fetch_live_weather(self):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.API_URL)
                if resp.status_code == 200:
                    data = resp.json()
                    # Data is usually ["time_tag", "Kp", "a_running", "station_count"]
                    # We get the most recent data point
                    if len(data) > 1:
                        latest = data[-1]
                        self.current_kp = float(latest[1])
                        self.storm_active = self.current_kp >= 5.0
                        
                        logger.info(f"[SPACE WEATHER] Live Kp Index updated to: {self.current_kp}. Storm: {self.storm_active}")
                        return self.current_kp
        except Exception as e:
            logger.warning(f"[SPACE WEATHER] NOAA API unreachable, using default parameters. Error: {e}")
        return self.current_kp

class WebhookNotifier:
    """Dispatches JSON payloads to external operations centers (e.g. Slack/Discord)."""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url
        
    async def send_alert(self, title: str, message: str, severity: str = "INFO"):
        logger.info(f"[WEBHOOK - {severity}] {title}: {message}")
        
        if not self.webhook_url:
            return # Mock mode if no URL defined
            
        color = 0x00FF00
        if severity == "WARNING": color = 0xFFA500
        if severity == "CRITICAL": color = 0xFF0000
            
        payload = {
            "embeds": [{
                "title": f"🚀 AETHER ALERT: {title}",
                "description": message,
                "color": color,
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }]
        }
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                await client.post(self.webhook_url, json=payload)
        except Exception as e:
            logger.error(f"Failed to dispatch webhook: {e}")
