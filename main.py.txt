import time
import logging
from config.settings import settings
from ui.dashboard import run_dashboard
import subprocess
import os

# लॉगिंग कॉन्फ़िगरेशन
os.makedirs(os.path.dirname(settings.LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=settings.LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def start_terminal():
    logging.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    print(f"--- Launching {settings.PROJECT_NAME} ---")
    
    try:
        # स्ट्रीमलिट डैशबोर्ड को सबप्रोसेस के रूप में चलाएं
        dashboard_path = os.path.join(settings.BASE_DIR, "ui", "dashboard.py")
        subprocess.run(["streamlit", "run", dashboard_path])
    except KeyboardInterrupt:
        logging.info("Terminal shutdown initiated by user.")
        print("\nShutdown signal received.")
    except Exception as e:
        logging.critical(f"Critical failure in terminal execution: {e}")

if __name__ == "__main__":
    start_terminal()
