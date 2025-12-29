import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


@app.get("/")
def home():
    return jsonify({
        "status": "ok",
        "message": "SOP Review Agent is running"
    })


@app.get("/debug/env")
def debug_env():
    key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "OPENAI_API_KEY_present": bool(key),
        "OPENAI_API_KEY_length": len(key) if key else 0,
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
        "TEST_RUNTIME": os.getenv("TEST_RUNTIME")
    })


@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = (data.get("sop_text") or "").strip()

    if not sop_text:
        return jsonify({"error": "sop_text is required"}), 400

    api_key = os.getenv("OPENAI_API_KEY") or request.headers.get("X-OPENAI-KEY")

    if not api_key:
        return jsonify({
            "error": "OpenAI API key missing. Set OPENAI_API_KEY or send X-OPENAI-KEY header."
        }), 500

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a senior Quality Assurance and Process Excellence expert.\n\n"
        "You MUST:\n"
        "- Review the SOP conservatively\n"
        "- Use only the given text\n"
        "- NOT assume missing info\n"
        "- NOT claim compliance\n"
        "- Return ONLY valid JSON\n"
        "- Follow the exact schema\n\n"
        "Evaluate using:\n"
        "1. Clarity & Readability\n"
        "2. Completeness\n"
        "3. Compliance Readiness\n"
        "4. Risk & Ambiguity\n"
        "5. Consistency\n"
        "6. Audit Readiness\n\n"
        "Return strictly this JSON schema:\n"
        "{\n"
        '  "overall_score": number,\n'
        '  "summary": string,\n'
        '  "dimensions": [\n'
        "    {\n"
        '      "name": string,\n'
        '      "score": number,\n'
        '      "issues": [string],\n'
        '      "suggestions": [string]\n'
        "    }\n"
        "  ],\n"
        '  "top_3_fixes": [string]\n'
        "}\n"
    )

    user_prompt = (
        "Review the following SOP:\n\n"
        "<START SOP>\n"
        f"{sop_text}\n"
        "<END SOP>\n"
    )

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

# ---- FIX overall_score deterministically ----
try:
    scores = [d.get("score", 0) for d in result.get("dimensions", [])]
    total = sum(float(s) for s in scores)
    result["overall_score"] = round((total * 100.0) / 60.0, 0)
except Exception:
    pass
# -------------------------------------------

return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": "AI review failed",
            "details": str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)

