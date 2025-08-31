import os
import uuid
import json
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import storage, pubsub_v1, firestore
import firebase_admin
from firebase_admin import credentials, auth

# --- إعدادات التطبيق ---
load_dotenv()
PROJECT_ID = "translation-470421-f18e8" # <-- استخدم معرف مشروع Firebase هنا
BUCKET_NAME = "amcai"
PUB_SUB_TOPIC = "amcai"

# --- إعداد Firebase Admin SDK ---
try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
except ValueError:
    print("تحذير: لم يتم تهيئة Firebase Admin SDK.")
db = firestore.client()
# -----------------------------

app = Flask(__name__, static_folder='static')
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)

def verify_token(request):
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '): return None
    id_token = auth_header.split('Bearer ')[1]
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token['uid']
    except Exception as e:
        print(f"خطأ في التحقق من التوكن: {e}")
        return None

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/extract', methods=['POST'])
def start_extraction_job():
    uid = verify_token(request)
    if not uid: return jsonify(error="Unauthorized"), 401
    if 'file' not in request.files: return jsonify(error="No file part"), 400
    file = request.files['file']
    if file.filename == '': return jsonify(error="No selected file"), 400
    
    try:
        blob_name = f"{uid}/uploads/{uuid.uuid4()}_{secure_filename(file.filename)}"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.stream, content_type=file.mimetype)

        job_id = str(uuid.uuid4())
        job_ref = db.collection('users').document(uid).collection('jobs').document(job_id)
        job_ref.set({
            'status': 'pending', 'original_filename': file.filename,
            'file_path': blob_name, 'created_at': firestore.SERVER_TIMESTAMP
        })

        message_data = {"job_id": job_id, "uid": uid, "file_path": blob_name}
        publisher.publish(topic_path, json.dumps(message_data).encode("utf-8")).result()
        
        return jsonify(job_id=job_id)
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/jobs', methods=['GET'])
def get_user_jobs():
    uid = verify_token(request)
    if not uid: return jsonify(error="Unauthorized"), 401
    
    jobs_ref = db.collection('users').document(uid).collection('jobs').order_by('created_at', direction=firestore.Query.DESCENDING).limit(20).stream()
    jobs = []
    for job in jobs_ref:
        job_data = job.to_dict()
        job_data['id'] = job.id
        jobs.append(job_data)
    return jsonify(jobs)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
