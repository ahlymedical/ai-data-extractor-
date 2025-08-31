import os
import json
import uuid
import math
import base64
from flask import Flask, request
from dotenv import load_dotenv
import pandas as pd
import google.generativeai as genai
from google.cloud import storage, pubsub_v1

# --- إعدادات التطبيق والخدمات ---
load_dotenv()

# !!== غير هذه القيمة ==!!
BUCKET_NAME = "amcai"  # <--- استبدل هذا باسم المخزن الذي أنشأته

# إعداد مفتاح API الخاص بـ Gemini
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("لم يتم العثور على مفتاح GEMINI_API_KEY.")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"خطأ فادح عند إعداد واجهة برمجة التطبيقات: {e}")

# إعداد عملاء Google Cloud
storage_client = storage.Client()
bucket = storage_client.bucket(BUCKET_NAME)

app = Flask(__name__)

# --- التعليمات الدقيقة للذكاء الاصطناعي (Prompt) ---
EXTRACTION_PROMPT = """
أنت مساعد خبير في استخلاص البيانات بشكل منظم ومهمتك هي تحليل المستندات أو النصوص المقدمة لك. 
هذه البيانات تحتوي على قوائم لمقدمي خدمة طبية. 
المطلوب منك هو المرور على المحتوى بالكامل واستخلاص المعلومات التالية لكل مقدم خدمة تجده:

1.  **id**: يجب أن يكون معرفًا فريدًا. استخدم رقم تسلسلي مثل "CID000001", "CID000002", وهكذا.
2.  **governorate**: المحافظة.
3.  **area**: المنطقة أو الحي.
4.  **type**: نوع مقدم الخدمة (مثال: مستشفى، صيدلية، معمل).
5.  **specialty_main**: التخصص الرئيسي.
6.  **specialty_sub**: التخصص الفرعي (إذا وجد، وإلا كرر التخصص الرئيسي).
7.  **name**: اسم مقدم الخدمة.
8.  **address**: العنوان بالتفصيل.
9.  **hotline**: الخط الساخن (إذا وجد، يجب أن يكون كنص). إذا لم يوجد، استخدم `null`.
10. **phones**: قائمة بكل أرقام الهواتف الأخرى كقائمة من النصوص (array of strings). إذا لم توجد، استخدم `[]`.

**قواعد الإخراج النهائية (مهم جدًا):**
- يجب أن يكون إخراجك النهائي عبارة عن مصفوفة JSON واحدة `[...]` تحتوي على كائنات JSON لكل مقدم خدمة.
- لا تقم بتضمين أي نص أو شروحات أو ملاحظات قبل أو بعد مصفوفة JSON.
- لا تستخدم علامات markdown مثل ```json.
"""

def process_excel_file(file_blob, job_id):
    """
    يعالج ملفات Excel باستخدام نظام الدفعات المبتكر.
    """
    print(f"الوظيفة {job_id}: بدء معالجة ملف Excel...")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    # تحميل الملف من الذاكرة
    file_bytes = file_blob.download_as_bytes()
    df = pd.read_excel(file_bytes)
    print(f"الوظيفة {job_id}: تم قراءة {len(df)} سجلاً.")
    
    BATCH_SIZE = 200
    total_batches = math.ceil(len(df) / BATCH_SIZE)
    all_results = []

    for i in range(total_batches):
        print(f"الوظيفة {job_id}: معالجة الدفعة {i+1}/{total_batches}...")
        start_index = i * BATCH_SIZE
        end_index = start_index + BATCH_SIZE
        batch_df = df[start_index:end_index]
        
        data_as_text = batch_df.to_markdown(index=False)
        content_to_process = [EXTRACTION_PROMPT, data_as_text]

        response = model.generate_content(content_to_process)
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
        
        try:
            batch_json = json.loads(cleaned_text)
            if isinstance(batch_json, list):
                all_results.extend(batch_json)
        except json.JSONDecodeError:
            print(f"الوظيفة {job_id}: خطأ في فك تشفير JSON للدفعة {i+1}. يتم تجاهلها.")
            continue
            
    return all_results

def process_other_file(file_blob, job_id):
    """
    يعالج الملفات غير المنظمة (PDF, صور) مباشرة باستخدام Gemini.
    """
    print(f"الوظيفة {job_id}: بدء معالجة ملف {file_blob.content_type}...")
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    
    file_bytes = file_blob.download_as_bytes()
    content_to_process = [
        EXTRACTION_PROMPT,
        {"mime_type": file_blob.content_type, "data": file_bytes}
    ]
    
    response = model.generate_content(content_to_process)
    cleaned_text = response.text.strip().replace("```json", "").replace("```", "")
    
    return json.loads(cleaned_text)


# --- نقطة الدخول الرئيسية للعامل ---
@app.route('/', methods=['POST'])
def pubsub_handler():
    """
    يستقبل الرسائل من Pub/Sub ويبدأ عملية المعالجة.
    """
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        print(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]
    data = {}
    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        data = json.loads(base64.b64decode(pubsub_message["data"]).decode("utf-8").strip())
    
    job_id = data.get("job_id", "unknown_job")
    file_path = data.get("file_path", "")

    if not file_path:
        print(f"الوظيفة {job_id}: خطأ - الرسالة لا تحتوي على مسار الملف.")
        return "Invalid message", 204 # 204 No Content يخبر Pub/Sub بعدم إعادة إرسال الرسالة

    try:
        print(f"--- [ وظيفة جديدة مستلمة: {job_id} | الملف: {file_path} ] ---")
        
        # تحميل الملف من Cloud Storage
        source_blob = bucket.blob(file_path)
        if not source_blob.exists():
            print(f"الوظيفة {job_id}: خطأ - الملف {file_path} غير موجود في المخزن.")
            return "File not found", 204
        
        # تحديث نوع المحتوى (مهم جدًا)
        source_blob.reload()
        file_content_type = source_blob.content_type

        final_results = []
        excel_mimetypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/vnd.ms-excel'
        ]

        # تحديد طريقة المعالجة بناءً على نوع الملف
        if file_content_type in excel_mimetypes:
            final_results = process_excel_file(source_blob, job_id)
        else:
            final_results = process_other_file(source_blob, job_id)
        
        if not final_results:
             raise ValueError("فشلت عملية الاستخلاص بالكامل، لم يتم العثور على بيانات.")

        # حفظ النتيجة النهائية
        output_filename = f"processed/{job_id}_result.json"
        destination_blob = bucket.blob(output_filename)
        destination_blob.upload_from_string(
            json.dumps(final_results, ensure_ascii=False, indent=4),
            content_type="application/json"
        )
        
        print(f"الوظيفة {job_id}: اكتملت بنجاح. تم حفظ النتيجة في {output_filename}")
        
        # في تطبيق حقيقي، ستقوم هنا بتحديث قاعدة بيانات (مثل Firestore)
        # لتخبر الواجهة الأمامية بأن الوظيفة قد اكتملت.

        return "Success", 204

    except Exception as e:
        print(f"الوظيفة {job_id}: فشلت المعالجة بسبب خطأ: {e}")
        # يمكنك هنا تسجيل الخطأ في قاعدة بيانات أو إرسال تنبيه
        return "Error processing file", 204


if __name__ == "__main__":
    # Gunicorn سيقوم بتشغيل التطبيق في بيئة الإنتاج
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
