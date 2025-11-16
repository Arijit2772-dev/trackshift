from flask import Flask, jsonify, send_from_directory
import os
import json

app = Flask(__name__)

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

def read_status(path):
    if not os.path.exists(path):
        return {"error": "status_file_not_found"}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        return {"error": str(e)}

@app.get("/sender-status")
def sender_status():
    path = os.path.join(PROJECT_ROOT, "sender", "sender_status.json")
    return jsonify(read_status(path))

@app.get("/receiver-status")
def receiver_status():
    path = os.path.join(PROJECT_ROOT, "receiver", "receiver_status.json")
    return jsonify(read_status(path))

@app.route("/")
def index():
    # serve static HTML from ./static/index.html
    return send_from_directory(os.path.join(PROJECT_ROOT, "static"), "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
