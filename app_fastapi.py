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
Path("prompts").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

CONFIG_FILE = "data/config.json"
PROMPTS_DIR = "prompts"
TEMPLATES_DIR = "templates"


def load_html_template() -> str:
    """从文件加载HTML模板"""
    template_file = Path(TEMPLATES_DIR) / "index.html"
    if template_file.exists():
        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()
    return "<h1>模板文件不存在</h1><p>请确保 templates/index.html 文件存在</p>"


def load_prompt_presets() -> dict:
    """从文件加载所有预设prompt模板"""
    presets = {}
    prompts_path = Path(PROMPTS_DIR)

    if prompts_path.exists():
        for file in prompts_path.glob("*.txt"):
            name = file.stem  # 文件名不含扩展名
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    presets[name] = f.read()
            except Exception as e:
                print(f"加载prompt文件失败 {file}: {e}")

    return presets


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
    """获取默认prompt（从文件加载第一个，或返回空）"""
    presets = load_prompt_presets()
    if presets:
        # 返回第一个预设
        return list(presets.values())[0]
    return "请总结以下论文内容：\n\n{content}"


@app.get("/", response_class=HTMLResponse)
async def index():
    """主页"""
    return load_html_template()


@app.get("/api/prompts")
async def get_prompts():
    """获取所有预设prompt模板"""
    presets = load_prompt_presets()
    # 确定默认预设
    default_key = sorted(presets.keys())[0] if presets else None
    return {
        'presets': presets,
        'default': default_key
    }


@app.post("/api/prompts/{name}")
async def save_prompt(name: str, request: Request):
    """保存prompt模板到文件"""
    data = await request.json()
    content = data.get('content', '')
    prompt_file = Path(PROMPTS_DIR) / f"{name}.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(content)
    return {"success": True}


@app.delete("/api/prompts/{name}")
async def delete_prompt(name: str):
    """删除prompt模板"""
    prompt_file = Path(PROMPTS_DIR) / f"{name}.txt"
    if prompt_file.exists():
        prompt_file.unlink()
        return {"success": True}
    return JSONResponse({"success": False, "message": "文件不存在"}, status_code=404)


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
