import os
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
workers = 1
threads = 4
timeout = 300   # AKShare first-run init takes ~150s; give it breathing room
