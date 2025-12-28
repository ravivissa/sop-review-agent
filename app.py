# 1️⃣ Imports (TOP of file)
from flask import Flask, request, jsonify

# 2️⃣ Create Flask app (TOP level – very important)
app = Flask(__name__)

# 3️⃣ Health / home route
@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "SOP Review Agent is running"})

# 4️⃣ SOP review endpoint
@app.post("/review")
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = data.get("sop_text", "")

    if not sop_text.strip():
        return jsonify({"error": "sop_text is required"}), 400

    return jsonify({
        "overall_score": 0,
        "summary": "AI scoring not enabled yet (Step 4).",
        "dimensions": [],
        "top_3_fixes": []
    })

# 5️⃣ (Optional) local run – gunicorn ignores this
if __name__ == "__main__":
    app.run()
