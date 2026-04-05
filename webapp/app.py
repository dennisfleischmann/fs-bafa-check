#!/usr/bin/env python3
from __future__ import annotations

import os

import gender_guesser.detector as gender
from flask import Flask, jsonify, request

app = Flask(__name__)
GENDER_DETECTOR = gender.Detector()


@app.route("/healthz", methods=["GET"])
def healthz():
    return {"ok": True}


@app.route("/api/salutation", methods=["GET"])
def api_salutation():
    firstname = (request.args.get("firstname") or "").strip()
    surname = (request.args.get("surname") or "").strip()

    if not firstname or not surname:
        return jsonify({"error": "Both 'firstname' and 'surname' query parameters are required."}), 400

    guessed_gender = GENDER_DETECTOR.get_gender(firstname)

    if guessed_gender in ("female", "mostly_female"):
        salutation = f"Sehr geehrte Frau {surname}"
    else:
        salutation = f"Sehr geehrter Herr {surname}"

    return jsonify({
        "firstname": firstname,
        "surname": surname,
        "guessed_gender": guessed_gender,
        "salutation": salutation,
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    debug = os.getenv("FLASK_DEBUG", "1") in {"1", "true", "True"}
    app.run(host="0.0.0.0", port=port, debug=debug)
