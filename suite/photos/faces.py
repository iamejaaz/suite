import base64
import hashlib
from pathlib import Path

import frappe
import requests

from suite.drive.utils.files import FileManager, storage_key

MODELS = {
    "detector": (
        "face_detection_yunet_2023mar.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "recognizer": (
        "face_recognition_sface_2021dec.onnx",
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79",
    ),
}
DETECT_SIDE = 1280
MIN_FACE = 48
MIN_SCORE = 0.85
SAME_PERSON = 0.55

_engine = None


def model_dir():
    return Path(frappe.get_app_path("suite", "photos", "models"))


def available():
    try:
        import cv2
    except ImportError:
        return False
    return all((model_dir() / name).exists() for name, _, _ in MODELS.values())


def setup_models():
    model_dir().mkdir(parents=True, exist_ok=True)
    for name, url, checksum in MODELS.values():
        target = model_dir() / name
        if target.exists() and _sha256(target) == checksum:
            print(f"{name} is ready")
            continue
        print(f"Downloading {name}")
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != checksum:
            frappe.throw(f"Checksum mismatch for {name}")
        target.write_bytes(response.content)


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _models():
    global _engine
    if _engine is None:
        import cv2

        detector = cv2.FaceDetectorYN.create(
            str(model_dir() / MODELS["detector"][0]), "", (320, 320), MIN_SCORE, 0.3, 50
        )
        recognizer = cv2.FaceRecognizerSF.create(str(model_dir() / MODELS["recognizer"][0]), "")
        _engine = (detector, recognizer)
    return _engine


def scan_file(file_name):
    metadata = frappe.db.get_value("Photo Metadata", file_name, ["name", "faces_scanned"], as_dict=True)
    if not metadata or metadata.faces_scanned or not available():
        return
    file = frappe.db.get_value("File", file_name, ["file_url", "mime_type", "owner"], as_dict=True)
    if not file or not (file.mime_type or "").startswith("image/"):
        return
    path = FileManager().site_folder / storage_key(file.file_url or "")
    if path.exists():
        for face in _detect(path):
            doc = frappe.get_doc({"doctype": "Photo Face", "file": file_name, **face}).insert(
                ignore_permissions=True
            )
            _assign(doc, file.owner)
    frappe.db.set_value("Photo Metadata", metadata.name, "faces_scanned", 1, update_modified=False)


def _detect(path):
    import cv2
    import numpy as np
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        rgb = ImageOps.exif_transpose(image).convert("RGB")
    scale = min(1.0, DETECT_SIDE / max(rgb.size))
    if scale < 1:
        rgb = rgb.resize((round(rgb.width * scale), round(rgb.height * scale)))
    frame = cv2.cvtColor(np.asarray(rgb), cv2.COLOR_RGB2BGR)
    height, width = frame.shape[:2]

    detector, recognizer = _models()
    detector.setInputSize((width, height))
    _, rows = detector.detect(frame)
    faces = []
    for row in rows if rows is not None else []:
        x, y, w, h = (float(v) for v in row[:4])
        if min(w, h) < MIN_FACE * scale or row[14] < MIN_SCORE:
            continue
        aligned = recognizer.alignCrop(frame, row)
        feature = recognizer.feature(aligned).flatten().astype("float32")
        feature /= np.linalg.norm(feature) or 1
        faces.append(
            {
                "x": max(0.0, x / width),
                "y": max(0.0, y / height),
                "width": min(1.0, w / width),
                "height": min(1.0, h / height),
                "score": float(row[14]),
                "embedding": _encode(feature),
            }
        )
    return faces


def _assign(face, owner):
    import numpy as np

    vector = _decode(face.embedding)
    best, best_score = None, SAME_PERSON
    for person in frappe.get_all(
        "Photo Person", filters={"owner": owner}, fields=["name", "centroid", "face_count"]
    ):
        score = float(np.dot(vector, _decode(person.centroid)))
        if score > best_score:
            best, best_score = person, score

    if best:
        count = best.face_count or 1
        centroid = _decode(best.centroid) * count + vector
        centroid /= np.linalg.norm(centroid) or 1
        frappe.db.set_value(
            "Photo Person",
            best.name,
            {"centroid": _encode(centroid), "face_count": count + 1},
            update_modified=False,
        )
        person = best.name
    else:
        doc = frappe.get_doc(
            {"doctype": "Photo Person", "centroid": face.embedding, "face_count": 1, "cover_face": face.name}
        )
        doc.insert(ignore_permissions=True)
        doc.db_set("owner", owner, update_modified=False)
        person = doc.name
    face.db_set("person", person, update_modified=False)
    _maybe_update_cover(person, face)


def _maybe_update_cover(person, face):
    cover = frappe.db.get_value("Photo Person", person, "cover_face")
    current = (
        frappe.db.get_value("Photo Face", cover, ["width", "height", "score"], as_dict=True)
        if cover
        else None
    )
    if not current or face.width * face.height * face.score > current.width * current.height * current.score:
        frappe.db.set_value("Photo Person", person, "cover_face", face.name, update_modified=False)


def recompute(person):
    import numpy as np

    faces = frappe.get_all("Photo Face", filters={"person": person}, fields=["name", "embedding"])
    if not faces:
        frappe.delete_doc("Photo Person", person, ignore_permissions=True, force=True)
        return
    centroid = sum(_decode(face.embedding) for face in faces)
    centroid /= np.linalg.norm(centroid) or 1
    frappe.db.set_value(
        "Photo Person",
        person,
        {"centroid": _encode(centroid), "face_count": len(faces)},
        update_modified=False,
    )
    cover = frappe.db.get_value("Photo Person", person, "cover_face")
    if not any(face.name == cover for face in faces):
        frappe.db.set_value("Photo Person", person, "cover_face", faces[0].name, update_modified=False)


def scan_all(user=None):
    filters = {"faces_scanned": 0}
    names = frappe.get_all("Photo Metadata", filters=filters, pluck="name")
    if user:
        owned = set(
            frappe.get_all("File", filters={"owner": user, "name": ["in", names or [""]]}, pluck="name")
        )
        names = [name for name in names if name in owned]
    for index, name in enumerate(names, 1):
        scan_file(name)
        if index % 20 == 0:
            frappe.db.commit()
            print(f"\rScanned {index}/{len(names)}", end="", flush=True)
    frappe.db.commit()
    print(f"\rScanned {len(names)} photos")


def face_crop(face, size=256):
    from PIL import Image, ImageOps

    path = FileManager().site_folder / storage_key(frappe.db.get_value("File", face.file, "file_url") or "")
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    side = max(face.width * width, face.height * height) * 1.6
    cx = (face.x + face.width / 2) * width
    cy = (face.y + face.height / 2) * height
    box = (
        max(0, cx - side / 2),
        max(0, cy - side / 2),
        min(width, cx + side / 2),
        min(height, cy + side / 2),
    )
    return image.crop(box).resize((size, size))


def _encode(vector):
    return base64.b64encode(vector.astype("float32").tobytes()).decode()


def _decode(value):
    import numpy as np

    return np.frombuffer(base64.b64decode(value), dtype="float32")
