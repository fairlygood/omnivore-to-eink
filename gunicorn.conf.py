# Gunicorn configuration file
import multiprocessing
wsgi_app = "wsgi:app"
workers = multiprocessing.cpu_count() * 2 + 1
bind = "0.0.0.0:5000"
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True
pidfile = "/var/run/gunicorn/prod.pid"
daemon = False