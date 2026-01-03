from flask import Flask, request, jsonify
import os
import json
from openai import OpenAI

from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
import docx  # python-docx


app = Flask(__name__)

# -------------------------
# Config
# -------------------------
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_CHARS_FOR_REVIEW = 18000  # keep it safe for MVP; can increase later

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# -------------------------
# Helpers
# -------------------------
def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set on server")
    return OpenAI(api_key=api_key)

def compute_overall_score(dimensions):
    try:
        scores = [float(d.get("score", 0)) for d in dimensions]
        return round((sum(scores) / 60.0) * 100.0, 0)
    except Exception:
        return None

def extract_text_from_pdf(file_stream) -> str:
    reader = PdfReader(file_stream)
    parts = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        if txt.strip():
            parts.append(txt)
    return "\n\n".join(parts).strip()

def extract_text_from_docx(file_stream) -> str:
    d = docx.Document(file_stream)
    paras = [p.text for p in d.paragraphs if p.text and p.text.strip()]
    return "\n".join(paras).strip()

def extract_text_from_txt(file_stream) -> str:
    raw = file_stream.read()
    # best-effort decode
    try:
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return str(raw)

def normalize_text(text: str) -> str:
    text = (text or "").strip()
    # limit size for MVP
    if len(text) > MAX_CHARS_FOR_REVIEW:
        text = text[:MAX_CHARS_FOR_REVIEW] + "\n\n[TRUNCATED FOR MVP]"
    return text


# -------------------------
# Health check
# -------------------------
from flask import redirect  # add this to your imports at the top

@app.get("/")
def home():
    return redirect("/review-ui")


# -------------------------
# Protected debug env
# -------------------------
@app.get("/debug/env")
def debug_env():
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
# Existing text UI
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
    a { text-decoration: none; }
  </style>
</head>

<body>
  <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap;">
    <div>
      <h2 style="margin:0;">SOP Review Agent</h2>
      <p class="hint" style="margin-top:8px; max-width:720px;">
        Paste an SOP (or upload a file) and get a structured audit-style review:
        scores across 6 dimensions, a short summary, and the top 3 fixes to apply first.
      </p>
      <p class="hint" style="margin-top:6px;">
        ✅ No login needed • 🔒 API key stays on the server • 🧾 Output is easy to share
      </p>

      <div style="margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;">
        <a href="/upload-ui" style="display:inline-block; padding:10px 12px; border:1px solid #ddd; border-radius:8px;">
          Upload SOP (PDF/DOCX/TXT)
        </a>
        <a href="#paste" style="display:inline-block; padding:10px 12px; border:1px solid #ddd; border-radius:8px;">
          Paste SOP Text Below
        </a>
      </div>
    </div>

    <div style="min-width:260px; border:1px solid #eee; border-radius:12px; padding:12px;">
      <div style="font-size:13px; color:#666; margin-bottom:6px;">Quick Start</div>
      <ol style="margin:0; padding-left:18px; font-size:13px; color:#333;">
        <li>Paste SOP text (or upload a file)</li>
        <li>Click <b>Review SOP</b></li>
        <li>Copy/share the results</li>
      </ol>
    </div>
  </div>

  <hr style="margin:18px 0; border:none; border-top:1px solid #eee;" />

  <div class="row" id="paste">
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

  <p class="hint" style="margin-top:14px;">
    Note: This is an AI-assisted review. For regulated processes, validate results with your compliance/audit team.
  </p>
</body>

</html>
"""


# -------------------------
# NEW Upload UI
# -------------------------
@app.get("/upload-ui")
def upload_ui():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>SOP Upload Review</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 980px; margin: 32px auto; padding: 0 16px; }
    input, button { font-size: 14px; }
    button { padding: 10px 14px; cursor: pointer; margin-top: 10px; }
    pre { background: #f5f5f5; padding: 14px; overflow: auto; border-radius: 8px; }
    .hint { color: #555; font-size: 13px; }
    a { text-decoration: none; }
  </style>
</head>
<body>
  <h2>Upload SOP File</h2>
  <p class="hint">
    Upload a .pdf, .docx, or .txt. Or go back to <a href="/review-ui">Text UI</a>.
  </p>

  <input type="file" id="file" />
  <br/>
  <button onclick="uploadAndReview()">Upload & Review</button>

  <h3>Result</h3>
  <pre id="result">{}</pre>

  <script>
    async function uploadAndReview() {
      const fileInput = document.getElementById("file");
      if (!fileInput.files || fileInput.files.length === 0) {
        alert("Please select a file first.");
        return;
      }

      document.getElementById("result").textContent = "Uploading and reviewing...";

      const formData = new FormData();
      formData.append("file", fileInput.files[0]);

      try {
        const res = await fetch("/upload", { method: "POST", body: formData });
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
# Review Endpoint (server key only)
# -------------------------
@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = normalize_text(data.get("sop_text"))

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
    {{"name":"Clarity & Readability","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Completeness","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Compliance Readiness","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Risk & Ambiguity","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Consistency","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Audit Readiness","score":0,"issues":[],"suggestions":[]}}
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
        result["overall_score"] = compute_overall_score(result.get("dimensions", []))

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "AI review failed", "details": str(e)}), 500


# -------------------------
# NEW Upload Endpoint
# -------------------------
@app.post("/upload")
def upload_and_review():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = secure_filename(f.filename)
    if not allowed_file(filename):
        return jsonify({"error": "Unsupported file type. Use pdf, docx, txt"}), 400

    ext = filename.rsplit(".", 1)[1].lower()

    try:
        if ext == "pdf":
            text = extract_text_from_pdf(f.stream)
        elif ext == "docx":
            text = extract_text_from_docx(f.stream)
        else:
            text = extract_text_from_txt(f.stream)

        text = normalize_text(text)
        if not text:
            return jsonify({"error": "Could not extract any text from the uploaded file"}), 400

        # Reuse the same review logic by calling /review function logic directly
        # (No HTTP call, just reuse code path)
        data = {"sop_text": text}
        # call review function logic by mimicking request: simpler: inline call
        # We'll just do the same as review_sop with the extracted text:

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
\"\"\"{text}\"\"\"

Return ONLY this JSON format:
{{
  "summary": "...",
  "dimensions": [
    {{"name":"Clarity & Readability","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Completeness","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Compliance Readiness","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Risk & Ambiguity","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Consistency","score":0,"issues":[],"suggestions":[]}},
    {{"name":"Audit Readiness","score":0,"issues":[],"suggestions":[]}}
  ],
  "top_3_fixes": []
}}
""".strip()

        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        result["overall_score"] = compute_overall_score(result.get("dimensions", []))
        result["source_file"] = filename
        result["extracted_chars"] = len(text)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": "Upload review failed", "details": str(e)}), 500


@app.post("/report-ui")
def report_ui():
    data = request.get_json(silent=True) or {}
    sop_text = data.get("sop_text", "")

    if not sop_text:
        return "SOP text missing", 400

    # Call internal review logic
    with app.test_request_context(json={"sop_text": sop_text}):
        review_response = review_sop()
        if isinstance(review_response, tuple):
            return "Review failed", 500
        result = review_response.get_json()

    overall = result.get("overall_score", 0)
    summary = result.get("summary", "")
    dims = result.get("dimensions", [])
    fixes = result.get("top_3_fixes", [])

    def color(score):
        if score >= 7: return "green"
        if score >= 4: return "orange"
        return "red"

    rows = ""
    for d in dims:
        rows += f"""
        <tr>
          <td>{d['name']}</td>
          <td>{d['score']}/10</td>
          <td style="color:{color(d['score'])}">{color(d['score']).upper()}</td>
        </tr>
        """

    fixes_html = "".join(f"<li>{f}</li>" for f in fixes)

    return f"""
<!doctype html>
<html>
<head>
  <title>SOP Review Report</title>
  <style>
    body {{ font-family: Arial; max-width: 900px; margin: auto; padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; }}
    td, th {{ border: 1px solid #ddd; padding: 8px; }}
    th {{ background: #f2f2f2; }}
  </style>
</head>
<body>
  <h1>SOP Quality Report</h1>
  <h2>Overall Score: {overall} / 100</h2>
  <p><b>Summary:</b> {summary}</p>

  <h3>Dimension Scores</h3>
  <table>
    <tr><th>Dimension</th><th>Score</th><th>Status</th></tr>
    {rows}
  </table>

  <h3>Top 3 Fixes</h3>
  <ul>{fixes_html}</ul>
</body>
</html>
"""


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)




