import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

# -------------------------------------------------
# App setup
# -------------------------------------------------
app = Flask(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# -------------------------------------------------
# Health check
# -------------------------------------------------
@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "SOP Review Agent is running"
    })

# -------------------------------------------------
# DEBUG: Environment variable visibility
# SAFE: does NOT expose key value
# -------------------------------------------------
@app.get("/debug/env")
def debug_env():
    key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "OPENAI_API_KEY_present": bool(key),
        "OPENAI_API_KEY_length": len(key) if key else 0,
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
        "TEST_RUNTIME": os.getenv("TEST_RUNTIME"),
    })

# -------------------------------------------------
# SOP Review endpoint (AI)
# -------------------------------------------------
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

    system_prompt = """
You are a senior Quality Assurance and Process Excellence expert.

You MUST:
- Review the SOP conservatively
- Use only the given text
- NOT assume missing info
- NOT claim compliance
- Return ONLY valid JSON
- Follow the exact schema

Evaluate using:
1. Clarity & Readability
2. Completeness
3. Compliance Readiness
4. Risk & Ambiguity
5. Consistency
6. Audit Readiness

Return strictly this JSON schema:
{
  "overall_score": number,
  "summary": string,
  "dimensions": [
    {
      "name": string,
      "score": number,
      "issues": [string],
      "suggestions": [string]
    }
  ],
  "top_3_fixes": [string]
}
"""

    user_prompt = f"""
Review the following SOP:

<START SOP>
{sop_text}
<END SOP>
"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2
        )

        result = json.loads(response.choices[0].message.content)
        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "AI review failed",
            "details": str(e)
        }), 500


# -------------------------------------------------
# Local run (ignored by gunicorn)
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
