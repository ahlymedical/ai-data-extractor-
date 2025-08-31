import os
import json
import base64
from flask import Flask, request
from dotenv import load_dotenv
import pandas as pd
import google.generativeai as genai
from google.cloud import storage, firestore
import firebase_admin
from firebase_admin import credentials
import math
from datetime import timedelta

# --- إعدادات التطبيق ---
load_dotenv()
PROJECT_ID = "translation-470421-f18e8"
BUCKET_NAME = "amcai"

try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred, {'projectId': PROJECT_ID})
except ValueError:
    print("Warning: Firebase Admin SDK not initialized.")
db = firestore.client()

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)
app = Flask(__name__)

EXTRACTION_PROMPT = """ ... """ # <-- الصق البرومبت الكامل هنا

def process_excel_file(file_blob, job_id):
    # ... (انسخ دالة process_excel_file الكاملة من الكود السابق هنا) ...
    return [] # Placeholder

def process_other_file(file_blob, job_id):
    # ... (انسخ دالة process_other_file الكاملة من الكود السابق هنا) ...
    return {} # Placeholder


@app.route('/', methods=['POST'])
def pubsub_handler():
    envelope = request.get_json()
    if not envelope or "message" not in envelope:
        return "Invalid message format", 400

    pubsub_message = envelope["message"]
    data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8").strip())
    
    job_id, uid, file_path = data.get("job_id"), data.get("uid"), data.get("file_path")
    if not all([job_id, uid, file_path]):
        return "Missing data", 400

    job_ref = db.collection('users').document(uid).collection('jobs').document(job_id)

    try:
        job_ref.update({'status': 'processing', 'worker_start_time': firestore.SERVER_TIMESTAMP})
        
        source_blob = bucket.blob(file_path)
        if not source_blob.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        source_blob.reload()
        file_content_type = source_blob.content_type
        
        # ... (نفس منطق المعالجة الهجين السابق) ...
        # final_results = ...
        
        output_filename = f"{uid}/processed/{job_id}_result.json"
        destination_blob = bucket.blob(output_filename)
        destination_blob.upload_from_string(json.dumps(final_results, ensure_ascii=False, indent=4), content_type="application/json")
        
        download_url = destination_blob.generate_signed_url(version="v4", expiration=timedelta(days=7))

        job_ref.update({
            'status': 'completed', 'result_path': output_filename,
            'download_url': download_url, 'completed_at': firestore.SERVER_TIMESTAMP
        })
        
        return "Success", 204
    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        job_ref.update({'status': 'failed', 'error': str(e)})
        return "Error", 204

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
