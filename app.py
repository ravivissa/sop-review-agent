from flask import Flask, request, jsonify

app = Flask(__name__)   # <-- THIS LINE MUST EXIST

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "SOP Review Agent is running"})

@app.route("/review", methods=["POST"])
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
