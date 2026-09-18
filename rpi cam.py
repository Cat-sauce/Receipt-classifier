from flask import Flask, send_file
import subprocess
import os

app = Flask(__name__)
PHOTO_PATH = "pi_shot.jpg"

@app.route("/capture")
def capture():
    subprocess.run([
        "rpicam-still", "-t", "1000", "-o", PHOTO_PATH,
        "--width", "1920", "--height", "1080", "-n"
    ], check=True)
    return send_file(PHOTO_PATH, mimetype="image/jpeg")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
