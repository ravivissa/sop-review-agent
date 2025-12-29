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
# Simple Browser UI
# -------------------------
@app.get("/review-ui")
def review_ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>SOP Review Agent</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 980px; margin: 32px auto; padding: 0 16px; }
    textarea { width: 100%; font-size: 14px; padding: 12px; }
    input { width: 100%; font-size: 14px; padding: 10px; }
    button { padding: 10px 14px; font-size: 14px; cursor: pointer; margin-top: 10px; }
    pre { background: #f5f5f5; padding: 14px; overflow: auto; border-radius: 8px; }
    .row { margin: 12px 0; }
    .hint { color: #555; font-size: 13px; }
  </style>
</head>
<body>
  <h2>SOP Review Agent</h2>
  <p class="hint">
    Paste SOP text, optionally paste your OpenAI key for testing (header-based).
    For production, you’ll store the key server-side (once Railway env vars are reliable).
  </p>

  <div class="row">
    <label><b>OpenAI API Key (optional for testing)</b></label>
    <input id="key" type="password" placeholder="sk-... (optional)" />
    <div class="hint">If empty, app will try OPENAI_API_KEY env var.</div>
  </div>

  <div class="row">
    <label><b>SOP Text</b></label>
    <textarea id="sop" rows="10" placeholder="Paste SOP text here..."></textarea>
  </div>

  <button onclick="submitReview()">Review SOP</button>

  <h3>Result</h3>
  <pre id="result">{}</pre>

  <script>
    async function submitReview() {
      const sopText = document.getElementById("sop").value || "";
      const apiKey = document.getElementById("key").value || "";

      document.getElementById("result").textContent = "Running review...";

      const headers = { "Content-Type": "application/json" };
      if (apiKey.trim().length > 0) {
        headers["X-OPENAI-KEY"] = apiKey.trim();
      }

      try {
        const res = await fetch("/review", {
          method: "POST",
          headers,
          body: JSON.stringify({ sop_text: sopText })
        });

        const data = await res.json();
        document.getElementById("result").textContent = JSON.stringify(data, null, 2);
      } catch (err) {
        document.getElementById("result").textContent = "Error: " + err;
      }
    }
  </script>
</body>
</html>
"""


# -------------------------
# SOP Review Endpoint
# -------------------------
@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = data.get("sop_text")

    if not sop_text or not str(sop_text).strip():
        return jsonify({"error": "sop_text is required"}), 400

    sop_text = str(sop_text).strip()

    # Priority: header key → env key
    api_key = request.headers.get("X-OPENAI-KEY") or os.getenv("OPENAI_API_KEY")

    if not api_key:
        return jsonify({
            "error": "OpenAI API key missing. Set OPENAI_API_KEY or send X-OPENAI-KEY header."
        }), 400

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

Return ONLY this JSON format:
{{
  "summary": "...",
  "dimensions": [
    {{
      "name": "Clarity & Readability",
      "score": 0,
      "issues": [],
      "suggestions": []
    }},
    {{
      "name": "Completeness",
      "score": 0,
      "issues": [],
      "suggestions": []
    }},
    {{
      "name": "Compliance Readiness",
      "score": 0,
      "issues": [],
      "suggestions": []
    }},
    {{
      "name": "Risk & Ambiguity",
      "score": 0,
      "issues": [],
      "suggestions": []
    }},
    {{
      "name": "Consistency",
      "score": 0,
      "issues": [],
      "suggestions": []
    }},
    {{
      "name": "Audit Readiness",
      "score": 0,
      "issues": [],
      "suggestions": []
    }}
  ],
  "top_3_fixes": []
}}
"""

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}
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


if __name__ == "__main__":
    # Local runs only. Railway uses gunicorn.
    app.run(host="0.0.0.0", port=8080)
