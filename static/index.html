<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>أداة استخلاص البيانات الذكية</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root { --primary-color: #4285F4; --secondary-color: #34A853; --button-color: #006A4E; }
        body {
            font-family: 'Cairo', sans-serif;
            background-color: #f0f2f5;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            color: #333;
        }
        .container {
            background-color: #ffffff;
            padding: 40px 50px;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
            width: 100%;
            max-width: 700px;
            text-align: center;
            border-top: 5px solid var(--primary-color);
        }
        h1 {
            color: var(--primary-color);
            margin-bottom: 10px;
            font-size: 2em;
        }
        p {
            color: #666;
            margin-bottom: 30px;
            font-size: 1.1em;
        }
        .button {
            background-color: var(--button-color);
            color: white;
            padding: 12px 30px;
            border: none;
            border-radius: 6px;
            font-size: 1.1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            margin: 10px 5px;
        }
        .button:hover:not(:disabled) {
            background-color: #005a41;
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
        }
        .button:disabled {
            background-color: #ccc;
            cursor: not-allowed;
        }
        #file-input { display: none; }
        #file-info {
            font-weight: 600;
            color: var(--secondary-color);
            margin-top: 20px;
            min-height: 24px;
            display: block;
        }
        .status {
            margin-top: 25px;
            font-size: 1.1em;
            font-weight: 600;
            min-height: 25px;
            padding: 10px;
            border-radius: 6px;
            display: none;
        }
        .status.processing { background-color: #e9f5ff; color: #0056b3; }
        .status.error { background-color: #f8d7da; color: #721c24; }
        .status.success { background-color: #d4edda; color: #155724; }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid var(--primary-color);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            animation: spin 1s linear infinite;
            display: inline-block;
            margin-left: 10px;
            vertical-align: middle;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.2/css/all.min.css">
</head>
<body>
    <div class="container">
        <h1><i class="fas fa-robot"></i> أداة استخلاص البيانات الذكية</h1>
        <p>اختر ملفًا ثم اضغط على "بدء المعالجة" ليقوم الذكاء الاصطناعي بتحليله.</p>
        
        <input type="file" id="file-input" accept=".xlsx, .pdf, .doc, .docx, .png, .jpg, .jpeg">
        
        <button class="button" id="select-file-btn"><i class="fas fa-file-upload"></i> اختر ملف</button>
        <button class="button" id="process-file-btn" disabled><i class="fas fa-cogs"></i> بدء المعالجة</button>
        
        <span id="file-info">لم يتم اختيار أي ملف</span>
        
        <div class="status" id="status"></div>
        
        <a href="#" class="button" id="download-link" style="display: none;" download="network_data.json">
            <i class="fas fa-download"></i> تحميل الملف الناتج
        </a>
    </div>
    <script>
        const selectFileBtn = document.getElementById('select-file-btn');
        const processFileBtn = document.getElementById('process-file-btn');
        const fileInput = document.getElementById('file-input');
        const statusDiv = document.getElementById('status');
        const downloadLink = document.getElementById('download-link');
        const fileInfoDiv = document.getElementById('file-info');

        let selectedFile = null;

        selectFileBtn.addEventListener('click', () => fileInput.click());

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                // ==========================================================
                //  **هذا هو السطر الذي تم إصلاحه**
                //  نختار الملف الأول من قائمة الملفات [0]
                // ==========================================================
                selectedFile = fileInput.files[0]; 

                fileInfoDiv.textContent = `الملف المختار: ${selectedFile.name}`;
                processFileBtn.disabled = false;
                downloadLink.style.display = 'none';
                statusDiv.style.display = 'none';
            }
        });

        processFileBtn.addEventListener('click', async () => {
            if (!selectedFile) {
                alert('الرجاء اختيار ملف أولاً.');
                return;
            }

            processFileBtn.disabled = true;
            selectFileBtn.disabled = true;

            statusDiv.className = 'status processing';
            statusDiv.innerHTML = 'جاري تحليل الملف بالذكاء الاصطناعي... <div class="spinner"></div>';
            statusDiv.style.display = 'block';
            downloadLink.style.display = 'none';

            const formData = new FormData();
            formData.append('file', selectedFile);

            try {
                const response = await fetch('/extract', { method: 'POST', body: formData });
                const result = await response.json();

                if (!response.ok) throw new Error(result.error || 'حدث خطأ غير متوقع');
                
                statusDiv.className = 'status success';
                statusDiv.innerHTML = `<i class="fas fa-check-circle"></i> اكتمل الاستخلاص بنجاح!`;
                downloadLink.href = result.download_url;
                downloadLink.style.display = 'inline-block';

            } catch (error) {
                statusDiv.className = 'status error';
                statusDiv.innerHTML = `<i class="fas fa-exclamation-triangle"></i> فشل الاستخلاص: ${error.message}`;
            } finally {
                selectFileBtn.disabled = false;
            }
        });
    </script>
</body>
</html>
