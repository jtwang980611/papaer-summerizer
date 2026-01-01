import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from paper_summarizer import PaperSummarizer

app = FastAPI(title="PDF论文总结工具")

# 确保目录存在
Path("data").mkdir(exist_ok=True)
Path("summaries").mkdir(exist_ok=True)
Path("temp").mkdir(exist_ok=True)

CONFIG_FILE = "data/config.json"


def load_config() -> dict:
    """加载配置"""
    if os.path.exists(CONFIG_FILE) and os.path.getsize(CONFIG_FILE) > 0:
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {
        'provider': 'Gemini',
        'api_key': os.getenv('API_KEY', ''),
        'base_url': os.getenv('BASE_URL', ''),
        'model': os.getenv('MODEL', 'gemini-2.5-flash'),
        'prompt': ''
    }


def save_config(config: dict):
    """保存配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_default_prompt():
    """默认prompt"""
    return """设定角色： 会计与金融领域资深实证研究员。
任务： 对提供的学术论文进行深度解析，并严格按照以下结构输出。所有提及本文或文中引用的参考文献处，必须严格使用 作者 (年份) 格式。

## 1. 研究问题 (Research Question)
定义研究的科学问题及其在会计/金融理论中的定位。

## 2. 理论逻辑与假设 (Theory & Hypotheses)
阐述核心理论模型（如 Schumpeter (1934) 的创新理论、Jensen and Meckling (1976) 的代理理论等）及推导出的可检验假设。

## 3. 实证设计 (Research Design)
- **样本构建：** 样本区间、数据库来源（如 WRDS, CSMAR, Wind）、样本筛选标准。
- **关键变量：** 核心自变量 (X)、因变量 (Y) 的具体度量指标（Measures）及计算公式。
- **识别策略：** 采用的模型（如 DID, RDD, FE）及内生性处理方法（如 IV, PSM, Heckman）。

## 4. 核心发现 (Key Results)
总结主回归结果（系数方向、显著性、经济显著性）以及关键的稳健性检验结论。

## 5. 机制检验与异质性 (Mechanism & Heterogeneity)
- **路径分析：** 说明 X 影响 Y 的具体中介路径或调节效应。
- **分组差异：** 哪些样本组（如高 vs 低融资约束）效应更显著。

## 6. 学术贡献 (Academic Contribution)
归纳该研究对既有文献的边际改进，或在特定制度背景下的新发现。

## 7. 研究局限与启发 (Limitations & Future Research)
识别识别策略或变量定义上的局限，并思考其对后续研究的启发。

论文内容：
{content}"""


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF论文总结工具</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; color: #2c3e50; margin-bottom: 20px; }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card h3 { margin-bottom: 15px; color: #34495e; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: 500; color: #555; }
        input, select, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 14px;
        }
        textarea { resize: vertical; min-height: 150px; }
        .row { display: flex; gap: 20px; flex-wrap: wrap; }
        .col { flex: 1; min-width: 300px; }
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.3s;
        }
        .btn-primary { background: #3498db; color: white; }
        .btn-primary:hover { background: #2980b9; }
        .btn-primary:disabled { background: #95a5a6; cursor: not-allowed; }
        .btn-secondary { background: #95a5a6; color: white; }
        .btn-secondary:hover { background: #7f8c8d; }
        .status {
            padding: 10px;
            border-radius: 4px;
            margin-top: 10px;
            display: none;
        }
        .status.show { display: block; }
        .status.success { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .status.info { background: #cce5ff; color: #004085; }
        .result {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 4px;
            white-space: pre-wrap;
            font-family: monospace;
            max-height: 600px;
            overflow-y: auto;
        }
        .progress { display: none; margin-top: 10px; }
        .progress.show { display: block; }
        .progress-bar {
            height: 20px;
            background: #e9ecef;
            border-radius: 4px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #3498db;
            transition: width 0.3s;
        }
        .file-list { margin: 10px 0; }
        .file-item {
            padding: 5px 10px;
            background: #e9ecef;
            border-radius: 4px;
            margin: 5px 0;
            display: inline-block;
        }
        .download-link {
            display: inline-block;
            margin-top: 10px;
            padding: 10px 20px;
            background: #27ae60;
            color: white;
            text-decoration: none;
            border-radius: 4px;
        }
        .download-link:hover { background: #219a52; }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 PDF论文总结工具</h1>

        <div class="row">
            <div class="col">
                <div class="card">
                    <h3>⚙️ API配置</h3>
                    <div class="form-group">
                        <label>API提供商</label>
                        <select id="provider">
                            <option value="OpenAI">OpenAI</option>
                            <option value="Gemini" selected>Gemini</option>
                            <option value="Claude">Claude</option>
                            <option value="自定义">自定义</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>API密钥</label>
                        <input type="password" id="api_key" placeholder="输入API密钥">
                    </div>
                    <div class="form-group">
                        <label>API基础URL</label>
                        <input type="text" id="base_url" placeholder="例如: https://your-api-url/v1">
                    </div>
                    <div class="form-group">
                        <label>模型名称</label>
                        <input type="text" id="model" value="gemini-2.5-flash" placeholder="模型名称">
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="save_config" checked> 自动保存配置
                        </label>
                    </div>
                    <button class="btn btn-secondary" onclick="saveConfig()">💾 保存配置</button>
                    <div id="config-status" class="status"></div>
                </div>

                <div class="card">
                    <h3>📝 自定义Prompt</h3>
                    <div class="form-group">
                        <textarea id="prompt" placeholder="使用 {content} 作为论文内容占位符"></textarea>
                    </div>
                    <button class="btn btn-secondary" onclick="resetPrompt()">🔄 恢复默认</button>
                </div>
            </div>

            <div class="col">
                <div class="card">
                    <h3>📂 上传PDF文件</h3>
                    <div class="form-group">
                        <input type="file" id="files" multiple accept=".pdf">
                    </div>
                    <div id="file-list" class="file-list"></div>
                    <button class="btn btn-primary" id="submit-btn" onclick="processPapers()">🚀 开始总结</button>

                    <div id="progress" class="progress">
                        <p id="progress-text">处理中...</p>
                        <div class="progress-bar">
                            <div id="progress-fill" class="progress-fill" style="width: 0%"></div>
                        </div>
                    </div>

                    <div id="status" class="status"></div>
                </div>

                <div class="card">
                    <h3>📄 总结结果</h3>
                    <div id="result" class="result">等待处理...</div>
                    <div id="download-container"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const defaultPrompt = `设定角色： 会计与金融领域资深实证研究员。
任务： 对提供的学术论文进行深度解析，并严格按照以下结构输出。

## 1. 研究问题 (Research Question)
定义研究的科学问题及其在会计/金融理论中的定位。

## 2. 理论逻辑与假设 (Theory & Hypotheses)
阐述核心理论模型及推导出的可检验假设。

## 3. 实证设计 (Research Design)
- **样本构建：** 样本区间、数据库来源、样本筛选标准。
- **关键变量：** 核心自变量 (X)、因变量 (Y) 的具体度量指标。
- **识别策略：** 采用的模型及内生性处理方法。

## 4. 核心发现 (Key Results)
总结主回归结果以及关键的稳健性检验结论。

## 5. 机制检验与异质性 (Mechanism & Heterogeneity)
- **路径分析：** 说明 X 影响 Y 的具体中介路径或调节效应。
- **分组差异：** 哪些样本组效应更显著。

## 6. 学术贡献 (Academic Contribution)
归纳该研究对既有文献的边际改进。

## 7. 研究局限与启发 (Limitations & Future Research)
识别研究局限，并思考其对后续研究的启发。

论文内容：
{content}`;

        // 加载配置
        async function loadConfig() {
            try {
                const resp = await fetch('/api/config');
                const config = await resp.json();
                document.getElementById('provider').value = config.provider || 'Gemini';
                document.getElementById('api_key').value = config.api_key || '';
                document.getElementById('base_url').value = config.base_url || '';
                document.getElementById('model').value = config.model || 'gemini-2.5-flash';
                document.getElementById('prompt').value = config.prompt || defaultPrompt;
            } catch (e) {
                console.error('加载配置失败', e);
            }
        }

        // 保存配置
        async function saveConfig() {
            const config = {
                provider: document.getElementById('provider').value,
                api_key: document.getElementById('api_key').value,
                base_url: document.getElementById('base_url').value,
                model: document.getElementById('model').value,
                prompt: document.getElementById('prompt').value
            };

            try {
                const resp = await fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(config)
                });
                showStatus('config-status', '✅ 配置已保存', 'success');
            } catch (e) {
                showStatus('config-status', '❌ 保存失败', 'error');
            }
        }

        // 重置prompt
        function resetPrompt() {
            document.getElementById('prompt').value = defaultPrompt;
        }

        // 显示状态
        function showStatus(id, msg, type) {
            const el = document.getElementById(id);
            el.textContent = msg;
            el.className = 'status show ' + type;
            setTimeout(() => el.className = 'status', 3000);
        }

        // 文件选择显示
        document.getElementById('files').addEventListener('change', function() {
            const list = document.getElementById('file-list');
            list.innerHTML = '';
            for (const file of this.files) {
                const item = document.createElement('span');
                item.className = 'file-item';
                item.textContent = file.name;
                list.appendChild(item);
            }
        });

        // 处理论文
        async function processPapers() {
            const files = document.getElementById('files').files;
            if (files.length === 0) {
                showStatus('status', '❌ 请选择PDF文件', 'error');
                return;
            }

            const apiKey = document.getElementById('api_key').value;
            if (!apiKey) {
                showStatus('status', '❌ 请输入API密钥', 'error');
                return;
            }

            // 禁用按钮
            const btn = document.getElementById('submit-btn');
            btn.disabled = true;
            btn.textContent = '处理中...';

            // 显示进度
            document.getElementById('progress').className = 'progress show';
            document.getElementById('result').textContent = '正在处理...';
            document.getElementById('download-container').innerHTML = '';

            // 保存配置
            if (document.getElementById('save_config').checked) {
                await saveConfig();
            }

            // 构建表单数据
            const formData = new FormData();
            for (const file of files) {
                formData.append('files', file);
            }
            formData.append('provider', document.getElementById('provider').value);
            formData.append('api_key', apiKey);
            formData.append('base_url', document.getElementById('base_url').value);
            formData.append('model', document.getElementById('model').value);
            formData.append('prompt', document.getElementById('prompt').value);

            try {
                const resp = await fetch('/api/summarize', {
                    method: 'POST',
                    body: formData
                });

                const result = await resp.json();

                if (result.success) {
                    document.getElementById('result').textContent = result.markdown;
                    showStatus('status', result.message, 'success');

                    if (result.file) {
                        document.getElementById('download-container').innerHTML =
                            `<a class="download-link" href="/download/${result.file}">📥 下载Markdown文件</a>`;
                    }
                } else {
                    showStatus('status', '❌ ' + result.message, 'error');
                    document.getElementById('result').textContent = '处理失败: ' + result.message;
                }
            } catch (e) {
                showStatus('status', '❌ 请求失败: ' + e.message, 'error');
                document.getElementById('result').textContent = '请求失败';
            }

            // 恢复按钮
            btn.disabled = false;
            btn.textContent = '🚀 开始总结';
            document.getElementById('progress').className = 'progress';
        }

        // 页面加载时加载配置
        loadConfig();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    return HTML_TEMPLATE


@app.get("/api/config")
async def get_config():
    """获取配置"""
    config = load_config()
    # 不返回完整的API密钥
    if config.get('api_key'):
        config['api_key'] = config['api_key']  # 前端需要密钥来发送请求
    return config


@app.post("/api/config")
async def update_config(request: Request):
    """保存配置"""
    config = await request.json()
    save_config(config)
    return {"success": True}


@app.post("/api/summarize")
async def summarize(
    files: list[UploadFile] = File(...),
    provider: str = Form(...),
    api_key: str = Form(...),
    base_url: str = Form(""),
    model: str = Form(...),
    prompt: str = Form("")
):
    """处理PDF并生成总结"""
    try:
        if not files:
            return JSONResponse({"success": False, "message": "请上传PDF文件"})

        if not api_key:
            return JSONResponse({"success": False, "message": "请输入API密钥"})

        # 创建总结器
        summarizer = PaperSummarizer(
            api_key=api_key,
            base_url=base_url if base_url else None,
            model=model
        )

        summaries = []
        temp_files = []

        for file in files:
            # 保存临时文件
            temp_path = f"temp/{file.filename}"
            with open(temp_path, "wb") as f:
                content = await file.read()
                f.write(content)
            temp_files.append(temp_path)

            try:
                custom_prompt = prompt if prompt else None
                summary_data = summarizer.summarize_paper(temp_path, custom_prompt)
                summaries.append(summary_data)
            except Exception as e:
                summaries.append({
                    "file_name": file.filename,
                    "summary": f"❌ 处理失败: {str(e)}",
                    "file_path": temp_path
                })

        # 清理临时文件
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except:
                pass

        # 生成Markdown
        md_content = "# 📚 论文总结合集\n\n"
        md_content += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md_content += f"**论文数量**: {len(summaries)}\n\n"
        md_content += "---\n\n"

        for i, summary_data in enumerate(summaries, 1):
            md_content += f"## 📄 {i}. {summary_data['file_name']}\n\n"
            md_content += f"{summary_data['summary']}\n\n"
            md_content += "---\n\n"

        # 保存文件
        output_filename = f"summaries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        output_path = f"summaries/{output_filename}"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        success_count = sum(1 for s in summaries if not s['summary'].startswith('❌'))

        return JSONResponse({
            "success": True,
            "message": f"✅ 成功处理 {success_count}/{len(summaries)} 篇论文",
            "markdown": md_content,
            "file": output_filename
        })

    except Exception as e:
        return JSONResponse({"success": False, "message": str(e)})


@app.get("/download/{filename}")
async def download(filename: str):
    """下载文件"""
    file_path = f"summaries/{filename}"
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="text/markdown")
    return JSONResponse({"error": "文件不存在"}, status_code=404)


def main():
    """启动应用"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7860,
        log_level="warning"  # 减少日志输出
    )


if __name__ == "__main__":
    main()
