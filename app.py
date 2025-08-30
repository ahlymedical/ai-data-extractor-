import os
import json
import uuid
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd
import math
import threading # <-- لاستخدام المعالجة في الخلفية

# --- إعدادات التطبيق ---
load_dotenv()
from tempfile import gettempdir
TEMP_FOLDER = gettempdir()

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# قاموس لتخزين حالة الوظائف (في تطبيق حقيقي، ستستخدم قاعدة بيانات مثل Redis)
JOBS = {}

# إعداد مفتاح API الخاص بـ Gemini
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("لم يتم العثور على مفتاح GEMINI_API_KEY.")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"خطأ فادح عند إعداد واجهة برمجة التطبيقات: {e}")

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

def process_file_in_background(job_id, file_path, original_filename):
    """
    هذه الدالة تعمل في الخلفية لمعالجة الملف دون إيقاف الخادم.
    """
    global JOBS
    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        df = pd.read_excel(file_path)
        
        BATCH_SIZE = 200
        total_batches = math.ceil(len(df) / BATCH_SIZE)
        all_results = []

        for i in range(total_batches):
            status_message = f"جاري معالجة الدفعة {i+1} من {total_batches}..."
            JOBS[job_id]['status'] = 'processing'
            JOBS[job_id]['progress'] = status_message
            print(f"الوظيفة {job_id}: {status_message}")

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
                print(f"[!] خطأ في الدفعة {i+1} للوظيفة {job_id}: فشل الذكاء الاصطناعي في توليد JSON صالح.")
                continue

        if not all_results:
            raise ValueError("فشلت عملية الاستخلاص بالكامل.")

        output_filename = f"{job_id}.json"
        output_path = os.path.join(TEMP_FOLDER, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
        
        JOBS[job_id]['status'] = 'completed'
        JOBS[job_id]['download_url'] = f"/download/{output_filename}"
        print(f"[+] اكتملت الوظيفة {job_id} بنجاح.")

    except Exception as e:
        print(f"[!] فشلت الوظيفة {job_id}: {e}")
        JOBS[job_id]['status'] = 'failed'
        JOBS[job_id]['error'] = str(e)


# --- نقاط النهاية (API Endpoints) ---

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
    
    # حفظ الملف مؤقتًا
    filename = secure_filename(file.filename)
    temp_path = os.path.join(TEMP_FOLDER, f"{uuid.uuid4()}_{filename}")
    file.save(temp_path)

    # إنشاء وظيفة جديدة
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {'status': 'pending', 'progress': 'في انتظار بدء المعالجة...'}

    # بدء المعالجة في الخلفية
    thread = threading.Thread(target=process_file_in_background, args=(job_id, temp_path, filename))
    thread.start()

    # الرد فورًا على المستخدم بهوية الوظيفة
    return jsonify(job_id=job_id)


@app.route('/status/<job_id>')
def get_job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        abort(404)
    return jsonify(job)

@app.route('/download/<filename>')
def download_file(filename):
    try:
        safe_filename = secure_filename(filename)
        return send_from_directory(
            TEMP_FOLDER,
            safe_filename,
            as_attachment=True,
            download_name="network_data.json"
        )
    except FileNotFoundError:
        abort(404)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
