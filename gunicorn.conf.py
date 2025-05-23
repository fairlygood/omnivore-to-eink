import multiprocessing

wsgi_app = "wsgi:app"
workers = multiprocessing.cpu_count() * 2 + 1
bind = "0.0.0.0:5001"
loglevel = "warning"
accesslog = "-"
errorlog = "-"
capture_output = True
pidfile = "/var/run/gunicorn/devel.pid"
daemon = False
timeout = 150
