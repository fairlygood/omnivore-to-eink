#!/bin/bash
gunicorn --worker-class eventlet -w 1 --config gunicorn.conf.py wsgi:app