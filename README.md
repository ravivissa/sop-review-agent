# SOP Review Agent (MVP)

## What this does
A simple API that will review SOP documents and return a structured scorecard.

## How to run locally (optional)
pip install -r requirements.txt
python app.py

## API endpoints
- GET / -> health check
- POST /review -> send SOP text and get review JSON

Example request:
{
  "sop_text": "Your SOP text here..."
}
