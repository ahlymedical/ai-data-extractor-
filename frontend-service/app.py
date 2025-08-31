import os
import uuid
import json
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import storage, pubsub_v1

# --- إعدادات التطبيق ---
load_dotenv()
# سيتم الحصول على معرف المشروع تلقائيًا من بيئة Google Cloud Run
PROJECT_ID = os.environ.get("GCP_PROJECT") 
BUCKET_NAME = "amcai"
PUB_SUB_TOPIC = "amcai"

# --- تم حذف كل أكواد Firebase من هنا لأنها غير ضرورية للواجهة وتسبب التعطل ---

app = Flask(__name__, static_folder='static')
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)

# --- نقاط النهاية (Endpoints) ---
@app.route('/')
def index():
    # التأكد من استخدام المسار المطلق لضمان العثور على المجلد دائمًا
    return send_from_directory(os.path.abspath('static'), 'index.html')

@app.route('/extract', methods=['POST'])
def start_extraction_job():
    # في هذه النسخة المبسطة، لن نتحقق من هوية المستخدم للتركيز على حل المشكلة الأساسية.
    # سنضيفها لاحقًا بعد التأكد من أن كل شيء يعمل.
    
    if 'file' not in request.files:
        return jsonify(error="لم يتم إرسال أي ملف"), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(error="لم يتم اختيار ملف"), 400
    
    try:
        # سيتم تنظيم الملفات لاحقًا بناءً على هوية المستخدم
        blob_name = f"uploads/{uuid.uuid4()}_{secure_filename(file.filename)}"
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file.stream, content_type=file.mimetype)

        job_id = str(uuid.uuid4())
        
        # إرسال الرسالة إلى العامل لبدء المعالجة
        message_data = {"job_id": job_id, "file_path": blob_name}
        publisher.publish(topic_path, json.dumps(message_data).encode("utf-8")).result()
        
        return jsonify(job_id=job_id, message="تم استلام الملف وبدء المعالجة في الخلفية.")

    except Exception as e:
        print(f"حدث خطأ في /extract: {e}")
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
