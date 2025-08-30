import os
import uuid
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from google.cloud import storage, pubsub_v1

# --- إعدادات التطبيق و Google Cloud ---
load_dotenv()

# استبدل هذه القيم بالأسماء التي اخترتها في الخطوة 1
PROJECT_ID = os.environ.get("GCP_PROJECT") # سيتم الحصول عليه تلقائيًا في Cloud Run
BUCKET_NAME = "aidata-files-storage-unique-name" # <-- غير هذا
PUB_SUB_TOPIC = "aidata-jobs-topic" # <-- غير هذا

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# إعداد عملاء Google Cloud
storage_client = storage.Client()
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)

# --- نقاط النهاية ---

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
        # 1. إنشاء اسم فريد للملف
        blob_name = f"uploads/{uuid.uuid4()}_{secure_filename(file.filename)}"
        
        # 2. رفع الملف إلى Google Cloud Storage
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(file)
        print(f"[*] تم رفع الملف بنجاح إلى GCS: {blob_name}")

        # 3. إرسال رسالة إلى Pub/Sub لبدء المعالجة
        job_id = str(uuid.uuid4())
        message_data = {
            "job_id": job_id,
            "file_name": blob_name,
            "bucket_name": BUCKET_NAME
        }
        
        # تحويل الرسالة إلى صيغة bytes
        future = publisher.publish(topic_path, json.dumps(message_data).encode("utf-8"))
        future.result() # التأكد من إرسال الرسالة
        
        print(f"[*] تم إرسال وظيفة جديدة {job_id} إلى Pub/Sub.")

        # 4. الرد فورًا على المستخدم بهوية الوظيفة
        return jsonify(job_id=job_id)

    except Exception as e:
        print(f"[!] حدث خطأ أثناء بدء الوظيفة: {e}")
        return jsonify(error=str(e)), 500

# ستحتاج إلى إضافة نقاط نهاية لمتابعة الحالة وتحميل الملف
# والتي ستقرأ من قاعدة بيانات (مثل Firestore) أو مخزن (Storage)
# تقوم خدمة "العامل" بتحديثه. هذا جزء متقدم يمكن إضافته لاحقًا.

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
