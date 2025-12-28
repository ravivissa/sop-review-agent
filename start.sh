#!/usr/bin/env bash
set -e

echo "Starting SOP Review Agent..."
gunicorn app:app --bind 0.0.0.0:$PORT
