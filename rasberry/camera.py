voici un base de code python connexion camera

from flask import Flask, Response, render_template_string
import cv2
import time

app = Flask(__name__)

CAMERA_INDEX = 0

# Réglages optimisés pour moins de latence
WIDTH = 640
HEIGHT = 360
FPS = 20
JPEG_QUALITY = 60

camera = cv2.VideoCapture(CAMERA_INDEX, cv2.CAP_V4L2)

# Important : utiliser MJPG si la caméra le supporte
camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

# Configuration caméra
camera.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
camera.set(cv2.CAP_PROP_FPS, FPS)

# Important : réduire le buffer pour éviter les anciennes images
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)

if not camera.isOpened():
    print("Erreur : impossible d'ouvrir la caméra /dev/video0")
    exit(1)

html_page = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Caméra Raspberry Pi</title>
    <style>
        body {
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
        }

        h1 {
            margin-top: 20px;
        }

        img {
            width: 90%;
            max-width: 900px;
            border: 3px solid white;
            border-radius: 10px;
        }

        .info {
            margin-top: 15px;
            color: #ccc;
        }
    </style>
</head>
<body>
    <h1>Flux caméra Raspberry Pi</h1>
    <img src="/video">
    <div class="info">
        Caméra USB → Raspberry Pi → PC externe
    </div>
</body>
</html>
"""

def generate_frames():
    # Qualité JPEG réduite pour rendre les images plus légères
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY]

    while True:
        success, frame = camera.read()

        if not success:
            print("Erreur : image non lue depuis la caméra")
            time.sleep(0.05)
            continue

        # Compression JPEG optimisée
        ret, buffer = cv2.imencode(".jpg", frame, encode_param)

        if not ret:
            print("Erreur : encodage JPEG impossible")
            continue

        frame_bytes = buffer.tobytes()

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
        )

@app.route("/")
def index():
    return render_template_string(html_page)

@app.route("/video")
def video():
    return Response(
        generate_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )

@app.route("/status")
def status():
    return {
        "camera": "connected",
        "device": "/dev/video0",
        "resolution": f"{WIDTH}x{HEIGHT}",
        "fps": FPS,
        "jpeg_quality": JPEG_QUALITY
    }

if __name__ == "__main__":
    print("Serveur caméra démarré")
    print("Page web : http://IP_DU_RASPBERRY:5000")
    print("Flux vidéo direct : http://IP_DU_RASPBERRY:5000/video")

    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)