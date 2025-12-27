from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "ok", "message": "SOP Review Agent is running"})

@app.route("/review", methods=["POST"])
def review_sop():
    data = request.get_json(silent=True) or {}
    sop_text = data.get("sop_text", "")

    if not sop_text.strip():
        return jsonify({"error": "sop_text is required"}), 400

    # Placeholder response (Step 4 will add real AI scoring)
    return jsonify({
        "overall_score": 0,
        "summary": "AI scoring not enabled yet (Step 4).",
        "dimensions": [],
        "top_3_fixes": []
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
