import os
import uuid
import json
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import storage, pubsub_v1

# --- إعدادات التطبيق و Google Cloud ---
load_dotenv()

# يجب الحصول على معرف المشروع تلقائيًا من بيئة Cloud Run
PROJECT_ID = os.environ.get("GCP_PROJECT") 

# !!== غير هذه القيم ==!!
BUCKET_NAME = "amcai"  # <--- استبدل هذا باسم المخزن الذي أنشأته
PUB_SUB_TOPIC = "amcai" # <--- استبدل هذا باسم الموضوع الذي أنشأته

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# إعداد عملاء Google Cloud
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/extract', methods=['POST'])
def start_extraction_job():
    if 'file' not in request.files:
        return jsonify(error="لم يتم إرسال أي ملف"), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(error="لم يتم اختيار ملف"), 400
    
    try:
        blob_name = f"uploads/{uuid.uuid4()}_{secure_filename(file.filename)}"
        
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        
        print(f"[*] يتم رفع الملف {file.filename} إلى {BUCKET_NAME}/{blob_name}...")
        blob.upload_from_file(file.stream)
        print(f"[+] تم الرفع بنجاح.")

        job_id = str(uuid.uuid4())
        message_data = {
            "job_id": job_id,
            "file_path": blob_name, # المسار داخل المخزن
        }
        
        future = publisher.publish(topic_path, json.dumps(message_data).encode("utf-8"))
        future.result()
        
        print(f"[*] تم إرسال وظيفة جديدة {job_id} إلى Pub/Sub.")
        
        return jsonify(job_id=job_id, message="تم استلام الملف وبدء المعالجة في الخلفية.")

    except Exception as e:
        print(f"[!] حدث خطأ أثناء بدء الوظيفة: {e}")
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
