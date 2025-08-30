import os
import json
import uuid
import mimetypes
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv

# --- إعدادات التطبيق والذكاء الاصطناعي ---
load_dotenv()

# استخدام مجلد مؤقت آمن يوفره نظام التشغيل بدلاً من مجلدات محلية
from tempfile import gettempdir
UPLOAD_FOLDER = gettempdir()
CONVERTED_FOLDER = gettempdir()

ALLOWED_EXTENSIONS = {'xlsx', 'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}

app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['CONVERTED_FOLDER'] = CONVERTED_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25 MB

# إعداد مفتاح API الخاص بـ Gemini
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("لم يتم العثور على مفتاح GEMINI_API_KEY في متغيرات البيئة.")
    genai.configure(api_key=api_key)
except Exception as e:
    print(f"خطأ فادح عند إعداد واجهة برمجة التطبيقات: {e}")

# --- التعليمات الدقيقة للذكاء الاصطناعي (Prompt) ---
EXTRACTION_PROMPT = """
أنت مساعد خبير في استخلاص البيانات بشكل منظم ومهمتك هي تحليل المستندات المقدمة لك. 
هذه المستندات تحتوي على قوائم لمقدمي خدمة طبية. 
المطلوب منك هو المرور على المستند بالكامل واستخلاص المعلومات التالية لكل مقدم خدمة تجده:

1.  **id**: يجب أن يكون معرفًا فريدًا. يمكنك استخدام رقم تسلسلي مثل "CID000001", "CID000002", وهكذا.
2.  **governorate**: المحافظة التي يقع بها مقدم الخدمة.
3.  **area**: المنطقة أو الحي.
4.  **type**: نوع مقدم الخدمة (مثال: مستشفى، صيدلية، معمل، مركز طبي، إلخ).
5.  **specialty_main**: التخصص الرئيسي (مثال: باطنة، عظام، صيدلية).
6.  **specialty_sub**: التخصص الفرعي (إذا وجد، وإلا كرر التخصص الرئيسي).
7.  **name**: اسم مقدم الخدمة.
8.  **address**: العنوان بالتفصيل.
9.  **hotline**: الخط الساخن (إذا وجد، يجب أن يكون كنص). إذا لم يوجد، استخدم `null`.
10. **phones**: قائمة بكل أرقام الهواتف الأخرى. يجب أن تكون قائمة من النصوص (array of strings). إذا لم توجد هواتف، استخدم قائمة فارغة `[]`.

**قواعد الإخراج النهائية (مهم جدًا):**
- يجب أن يكون إخراجك النهائي عبارة عن مصفوفة JSON واحدة `[...]` تحتوي على كائنات JSON لكل مقدم خدمة.
- لا تقم بتضمين أي نص أو شروحات أو ملاحظات قبل أو بعد مصفوفة JSON.
- لا تستخدم علامات markdown مثل ```json.
- كن دقيقًا جدًا في استخلاص البيانات وتأكد من تطابق أسماء الحقول تمامًا مع ما هو مطلوب أعلاه.
"""

# --- نقاط النهاية (API Endpoints) ---

@app.route('/')
def index():
    """يقدم صفحة الويب الرئيسية."""
    return send_from_directory('static', 'index.html')

@app.route('/extract', methods=['POST'])
def extract_data():
    if 'file' not in request.files:
        return jsonify(error="لم يتم إرسال أي ملف"), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(error="لم يتم اختيار ملف"), 400

    try:
        file_bytes = file.read()
        mime_type, _ = mimetypes.guess_type(file.filename)
        if not mime_type:
            mime_type = 'application/octet-stream'

        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        
        print(f"[*] يتم إرسال الملف {file.filename} ({mime_type}) إلى الذكاء الاصطناعي للتحليل...")
        response = model.generate_content([EXTRACTION_PROMPT, {"mime_type": mime_type, "data": file_bytes}])
        
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")

        try:
            json_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print(f"[!] خطأ: فشل الذكاء الاصطناعي في توليد JSON صالح. الرد كان:\n{response.text}")
            raise ValueError("لم يتمكن المساعد الذكي من استخلاص البيانات بصيغة صحيحة.")

        output_filename = f"{uuid.uuid4()}.json"
        # استخدام مسار آمن في المجلد المؤقت
        output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        
        print(f"[+] تم حفظ الملف المحول بنجاح: {output_filename}")
        
        return jsonify({
            "message": "تم استخلاص البيانات بنجاح!",
            "download_url": f"/download/{output_filename}"
        })

    except Exception as e:
        print(f"[!] حدث خطأ أثناء المعالجة: {e}")
        # إرجاع رسالة الخطأ الفعلية للمستخدم لتسهيل تصحيح الأخطاء
        return jsonify(error=str(e)), 500

@app.route('/download/<filename>')
def download_file(filename):
    """
    يسمح للمستخدم بتحميل ملف JSON الناتج.
    """
    try:
        # تأمين اسم الملف قبل استخدامه
        safe_filename = secure_filename(filename)
        return send_from_directory(
            app.config['CONVERTED_FOLDER'],
            safe_filename,
            as_attachment=True,
            download_name="network_data.json"
        )
    except FileNotFoundError:
        abort(404)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
