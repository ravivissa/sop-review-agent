from flask import Flask, request, jsonify
import os
import json
from openai import OpenAI

app = Flask(__name__)

# -------------------------
# Health check
# -------------------------
@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "SOP Review Agent is running"
    })


# -------------------------
# Debug env (safe)
# -------------------------
@app.get("/debug/env")
def debug_env():
    key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "OPENAI_API_KEY_present": bool(key),
        "OPENAI_API_KEY_length": len(key) if key else 0,
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
        "TEST_RUNTIME": os.getenv("TEST_RUNTIME")
    })


# -------------------------
# SOP Review Endpoint
# -------------------------
@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = data.get("sop_text")

    if not sop_text:
        return jsonify({"error": "sop_text is required"}), 400

    # Priority: header key → env key
    api_key = request.headers.get("X-OPENAI-KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        return jsonify({
            "error": "OpenAI API key missing. Set OPENAI_API_KEY or send X-OPENAI-KEY header."
        }), 400

    try:
        client = OpenAI(api_key=api_key)

        prompt = f"""
You are an SOP Quality Auditor.

Score the SOP strictly on 6 dimensions (0–10 each):
1. Clarity & Readability
2. Completeness
3. Compliance Readiness
4. Risk & Ambiguity
5. Consistency
6. Audit Readiness

Rules:
- Be strict
- Short SOPs score low
- Return ONLY valid JSON
- overall_score will be recalculated by system

SOP:
\"\"\"{sop_text}\"\"\"

JSON format:
{{
  "summary": "...",
  "dimensions": [
    {{
      "name": "Clarity & Readability",
      "score": 0,
      "issues": [],
      "suggestions": []
    }}
  ],
  "top_3_fixes": []
}}
"""

        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )

        result = json.loads(response.choices[0].message.content)

        # ---- Deterministic overall_score fix ----
        try:
            scores = [d.get("score", 0) for d in result.get("dimensions", [])]
            total = sum(float(s) for s in scores)
            result["overall_score"] = round((total * 100.0) / 60.0, 0)
        except Exception:
            result["overall_score"] = None
        # ----------------------------------------

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "AI review failed",
            "details": str(e)
        }), 500
