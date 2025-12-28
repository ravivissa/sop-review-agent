import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

import os
from flask import jsonify

@app.get("/debug/env")
def debug_env():
    key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "OPENAI_API_KEY_present": bool(key),
        "OPENAI_API_KEY_length": len(key) if key else 0,
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", None)
    })


MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "SOP Review Agent is running"
    })

@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = (data.get("sop_text") or "").strip()

    if not sop_text:
        return jsonify({"error": "sop_text is required"}), 400

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return jsonify({
            "error": "OPENAI_API_KEY not set in Railway variables"
        }), 500

    client = OpenAI(api_key=api_key)

    system_prompt = """You are a senior Quality Assurance and Process Excellence expert.

Return ONLY valid JSON. Do not add explanations.
"""

    user_prompt = f"""
Review the following SOP:

<START SOP>
{sop_text}
<END SOP>
"""

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )

        result = json.loads(resp.choices[0].message.content)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "AI review failed",
            "details": str(e)
        }), 500

