from flask import Flask, request, jsonify
import os
import json
from openai import OpenAI

app = Flask(__name__)

# -------------------------
# Helpers
# -------------------------
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set on server")
    return OpenAI(api_key=api_key)

def compute_overall_score(dimensions):
    # dimensions: list of {"score": 0-10}
    try:
        scores = [float(d.get("score", 0)) for d in dimensions]
        # normalize 0..60 -> 0..100
        return round((sum(scores) / 60.0) * 100.0, 0)
    except Exception:
        return None

# -------------------------
# Health check
# -------------------------
@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "SOP Review Agent is running"})

# -------------------------
# Protected debug env
# -------------------------
@app.get("/debug/env")
def debug_env():
    # Protect this endpoint so random users can't probe your server config
    required = os.getenv("DEBUG_TOKEN")
    provided = request.headers.get("X-DEBUG-TOKEN")

    if required and provided != required:
        return jsonify({"error": "Forbidden"}), 403

    key = os.getenv("OPENAI_API_KEY")
    return jsonify({
        "OPENAI_API_KEY_present": bool(key),
        "OPENAI_API_KEY_length": len(key) if key else 0,
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL"),
        "TEST_RUNTIME": os.getenv("TEST_RUNTIME")
    })

# -------------------------
# Browser UI (no key input)
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
    button { padding: 10px 14px; font-size: 14px; cursor: pointer; margin-top: 10px; }
    pre { background: #f5f5f5; padding: 14px; overflow: auto; border-radius: 8px; }
    .row { margin: 12px 0; }
    .hint { color: #555; font-size: 13px; }
  </style>
</head>
<body>
  <h2>SOP Review Agent</h2>
  <p class="hint">
    Paste SOP text and click Review. The server securely uses its own OpenAI key.
  </p>

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
      document.getElementById("result").textContent = "Running review...";

      try {
        const res = await fetch("/review", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
# Review endpoint (server key only)
# -------------------------
@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = (data.get("sop_text") or "").strip()

    if not sop_text:
        return jsonify({"error": "sop_text is required"}), 400

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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
""".strip()

    try:
        client = get_openai_client()

        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)

        # Ensure overall_score is deterministic & consistent
        dims = result.get("dimensions", [])
        result["overall_score"] = compute_overall_score(dims)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "AI review failed", "details": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
