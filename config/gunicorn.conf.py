import os

bind = "0.0.0.0:5000"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
timeout = 60
graceful_timeout = 30
accesslog = "-"
errorlog = "-"
capture_output = True
