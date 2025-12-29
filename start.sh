#!/usr/bin/env bash
set -e

echo "Starting SOP Review Agent"
echo "OPENAI_API_KEY length: ${#OPENAI_API_KEY}"

exec gunicorn app:app --bind 0.0.0.0:$PORT
