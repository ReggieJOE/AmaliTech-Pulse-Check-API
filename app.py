"""
app.py — Entry point for the Watchdog Sentinel API.

Run with:
    python app.py

Or with Flask CLI:
    flask --app app run
"""

from flask import Flask, jsonify
from routes import bp

app = Flask(__name__)

# Register all monitor routes
app.register_blueprint(bp)


# Health check — useful for uptime monitoring and load balancers
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "Watchdog Sentinel"}), 200


# 404 handler — return JSON instead of Flask's default HTML error page
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Endpoint not found."}), 404


# 405 handler — wrong HTTP method
@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed on this endpoint."}), 405


if __name__ == "__main__":
    # debug=False in production — set to True only during development
    app.run(host="0.0.0.0", port=5000, debug=True)
