import os
import json
import uuid
from flask import Flask, request, jsonify, send_from_directory, abort
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import pandas as pd
import math

# --- إعدادات التطبيق ---
load_dotenv()
from tempfile import gettempdir
TEMP_FOLDER = gettempdir()

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # زيادة الحد إلى 100MB

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
أنت مساعد خبير في استخلاص البيانات. سأعطيك جزءًا من جدول بيانات بصيغة Markdown.
مهمتك هي تحويل هذا الجزء فقط إلى مصفوفة JSON تحتوي على كائنات.
كل كائن يجب أن يحتوي على الحقول التالية بالضبط:
'id', 'governorate', 'area', 'type', 'specialty_main', 'specialty_sub', 'name', 'address', 'hotline', 'phones'.

**قواعد الإخراج (مهم جدًا):**
- يجب أن يكون إخراجك فقط مصفوفة JSON `[...]`.
- لا تقم بتضمين أي نص أو شروحات قبل أو بعد المصفوفة.
- لا تستخدم علامات markdown مثل ```json.
- تأكد من أن قيمة `hotline` هي نص (string) أو `null`.
- تأكد من أن قيمة `phones` هي مصفوفة من النصوص (array of strings).
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
        
        print(f"[*] تم استلام ملف: {file.filename}")
        df = pd.read_excel(file)
        print(f"[*] تم قراءة {len(df)} سجلاً من ملف Excel.")
        
        # ======================================================================
        #  **نظام المعالجة بالدفعات (Batch Processing)**
        # ======================================================================
        BATCH_SIZE = 200 # عدد السجلات في كل دفعة
        total_batches = math.ceil(len(df) / BATCH_SIZE)
        all_results = []

        for i in range(total_batches):
            start_index = i * BATCH_SIZE
            end_index = start_index + BATCH_SIZE
            batch_df = df[start_index:end_index]
            
            print(f"[*] تتم معالجة الدفعة {i+1} من {total_batches} (السجلات من {start_index} إلى {end_index})...")
            
            data_as_text = batch_df.to_markdown(index=False)
            content_to_process = [EXTRACTION_PROMPT, data_as_text]

            response = model.generate_content(content_to_process)
            cleaned_text = response.text.strip().replace("```json", "").replace("```", "")

            try:
                batch_json = json.loads(cleaned_text)
                if isinstance(batch_json, list):
                    all_results.extend(batch_json)
                else:
                    print(f"[!] تحذير: الدفعة {i+1} لم ترجع قائمة، تم تجاهلها.")

            except json.JSONDecodeError:
                print(f"[!] خطأ في الدفعة {i+1}: فشل الذكاء الاصطناعي في توليد JSON صالح. الرد كان:\n{response.text}")
                # يمكن اختيار الاستمرار أو إيقاف العملية هنا
                continue # استمرار للدُفعة التالية

        print(f"[*] اكتملت المعالجة. تم استخلاص {len(all_results)} سجلاً بنجاح.")
        # ======================================================================

        if not all_results:
            raise ValueError("فشلت عملية الاستخلاص بالكامل. لم يتم العثور على بيانات صالحة.")

        output_filename = f"{uuid.uuid4()}.json"
        output_path = os.path.join(TEMP_FOLDER, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, ensure_ascii=False, indent=4)
        
        print(f"[+] تم حفظ الملف المحول بنجاح: {output_filename}")
        
        return jsonify({
            "message": f"تم استخلاص {len(all_results)} سجلاً بنجاح!",
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
