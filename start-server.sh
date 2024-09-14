#!/bin/bash
gunicorn --config gunicorn.conf.py wsgi:app