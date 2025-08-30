import os
import json
import uuid
import mimetypes
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd # <-- تم استيراد المكتبة الجديدة لمعالجة Excel

# --- إعدادات التطبيق ---
load_dotenv()
from tempfile import gettempdir
TEMP_FOLDER = gettempdir()

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

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

# --- نقاط النهاية (API Endpoints) ---

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/extract', methods=['POST'])
def extract_data():
    if 'file' not in request.files:
        return jsonify(error="لم يتم إرسال أي ملف"), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(error="لم يتم اختيار ملف"), 400

    try:
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        content_to_process = None
        
        # ======================================================================
        #  **الحل الهجين المبتكر والفعال**
        #  التحقق من نوع الملف وتحديد أفضل طريقة للمعالجة
        # ======================================================================
        mime_type = file.mimetype
        print(f"[*] تم استلام ملف: {file.filename}, النوع: {mime_type}")

        # أنواع ملفات Excel التي ستتم معالجتها بواسطة Pandas
        excel_mimetypes = [
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', # .xlsx
            'application/vnd.ms-excel' # .xls
        ]

        if mime_type in excel_mimetypes:
            print("[*] تم اكتشاف ملف Excel. تتم المعالجة باستخدام Pandas...")
            # 1. قراءة بيانات Excel باستخدام Pandas
            df = pd.read_excel(file)
            # 2. تحويل البيانات إلى نص بسيط (صيغة Markdown مناسبة للذكاء الاصطناعي)
            data_as_text = df.to_markdown(index=False)
            # 3. تجهيز المحتوى لإرساله كنص
            content_to_process = [EXTRACTION_PROMPT, "الرجاء تحويل جدول البيانات التالي بصيغة Markdown إلى JSON:", data_as_text]
        
        else: # للملفات الأخرى (PDF, صور, Word)
            print("[*] تم اكتشاف ملف غير منظم (PDF/صورة/...). تتم المعالجة مباشرة عبر Gemini...")
            # 1. قراءة الملف كبيانات ثنائية (bytes)
            file_bytes = file.read()
            # 2. تجهيز المحتوى لإرساله كملف
            content_to_process = [EXTRACTION_PROMPT, {"mime_type": mime_type, "data": file_bytes}]

        # ======================================================================

        print("[*] يتم إرسال الطلب إلى الذكاء الاصطناعي...")
        response = model.generate_content(content_to_process)
        
        cleaned_text = response.text.strip().replace("```json", "").replace("```", "")

        try:
            json_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print(f"[!] خطأ: فشل الذكاء الاصطناعي في توليد JSON صالح. الرد كان:\n{response.text}")
            raise ValueError("لم يتمكن المساعد الذكي من استخلاص البيانات بصيغة صحيحة.")

        output_filename = f"{uuid.uuid4()}.json"
        output_path = os.path.join(TEMP_FOLDER, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)
        
        print(f"[+] تم حفظ الملف المحول بنجاح: {output_filename}")
        
        return jsonify({
            "message": "تم استخلاص البيانات بنجاح!",
            "download_url": f"/download/{output_filename}"
        })

    except Exception as e:
        print(f"[!] حدث خطأ أثناء المعالجة: {e}")
        return jsonify(error=str(e)), 500

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
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
