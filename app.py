import os
import json
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

# OpenAI client reads OPENAI_API_KEY from environment automatically
client = OpenAI()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a senior Quality Assurance and Process Excellence expert.

Your task is to review a Standard Operating Procedure (SOP) document and evaluate it objectively.

You MUST:
- Use only the content provided in the SOP
- NOT assume missing information
- NOT claim regulatory compliance
- Be conservative and factual
- Return output ONLY in valid JSON
- Follow the exact JSON schema provided
- Score fairly using the defined criteria
- Do NOT include markdown or extra text

Evaluate the SOP using these six dimensions:

1. Clarity & Readability
2. Completeness
3. Compliance Readiness (readiness only; do NOT claim compliance)
4. Risk & Ambiguity
5. Consistency
6. Audit Readiness

Scoring rules:
- Each dimension must be scored from 0 to 10
- Justify each score briefly using issues + suggestions
- Overall score = (sum of dimension scores × 100) / 60

Output MUST strictly follow this JSON schema and nothing else:
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

@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "SOP Review Agent is running"})

@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = (data.get("sop_text") or "").strip()

    if not sop_text:
        return jsonify({"error": "sop_text is required"}), 400

    user_prompt = f"""Review the following SOP:

<START SOP>
{sop_text}
<END SOP>
"""

    try:
        # Chat Completions with JSON-only output
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        raw = resp.choices[0].message.content or "{}"
        result = json.loads(raw)  # ensure valid JSON

        return jsonify(result)

    except Exception as e:
        # Return readable error (don’t leak secrets)
        return jsonify({"error": "AI review failed", "details": str(e)}), 500
