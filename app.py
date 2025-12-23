import gradio as gr
import os
import json
from pathlib import Path
from datetime import datetime
from paper_summarizer import PaperSummarizer


class PaperSummarizerApp:
    """Gradio应用包装器"""

    def __init__(self):
        # 配置文件存放在data目录（Docker卷挂载点）
        Path("data").mkdir(exist_ok=True)
        self.config_file = "data/config.json"
        # 确保summaries目录存在
        Path("summaries").mkdir(exist_ok=True)
        self.load_config()

    def load_config(self):
        """加载配置文件"""
        if os.path.exists(self.config_file) and os.path.getsize(self.config_file) > 0:
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.saved_provider = config.get('provider', 'Gemini')
                    self.saved_api_key = config.get('api_key', '')
                    self.saved_base_url = config.get('base_url', '')
                    self.saved_model = config.get('model', 'gemini-2.5-flash')
                    self.saved_prompt = config.get('prompt', '')
            except (json.JSONDecodeError, Exception) as e:
                print(f"配置文件加载失败: {e}，使用默认配置")
                self._load_default_config()
        else:
            # 文件不存在或为空，使用默认配置
            self._load_default_config()

    def _load_default_config(self):
        """加载默认配置"""
        self.saved_provider = 'Gemini'
        self.saved_api_key = os.getenv('API_KEY', '')
        self.saved_base_url = os.getenv('BASE_URL', '')
        self.saved_model = os.getenv('MODEL', 'gemini-2.5-flash')
        self.saved_prompt = ''

    def save_config(self, provider, api_key, base_url, model, prompt):
        """保存配置到文件"""
        try:
            config = {
                'provider': provider,
                'api_key': api_key,
                'base_url': base_url,
                'model': model,
                'prompt': prompt
            }
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return "✅ 配置已保存"
        except Exception as e:
            return f"❌ 保存失败: {str(e)}"

    def save_config_only(self, provider, api_key, base_url, model, prompt):
        """仅保存配置（供按钮调用）"""
        if not api_key:
            return "❌ 请输入API密钥"
        result = self.save_config(provider, api_key, base_url or '', model, prompt or '')
        return result

    def process_papers(self, files, provider, api_key, base_url, model, custom_prompt, save_config_flag, progress=gr.Progress()):
        """
        处理上传的PDF文件

        Args:
            files: 上传的PDF文件列表
            provider: API提供商
            api_key: API密钥
            base_url: API基础URL
            model: 模型名称
            custom_prompt: 自定义prompt
            save_config_flag: 是否保存配置
            progress: Gradio进度条对象

        Returns:
            markdown内容和状态消息
        """
        try:
            # 验证输入
            if not files:
                return "", "❌ 请上传至少一个PDF文件", None

            if not api_key:
                return "", "❌ 请输入API密钥", None

            # 保存配置（如果勾选）
            if save_config_flag:
                self.save_config(provider, api_key, base_url or '', model, custom_prompt or '')

            # 创建总结器
            summarizer = PaperSummarizer(
                api_key=api_key,
                base_url=base_url if base_url else None,
                model=model
            )

            # 处理每个文件
            summaries = []
            total_files = len(files)

            print(f"\n{'='*70}")
            print(f"📚 开始批量处理论文，共 {total_files} 篇")
            print(f"{'='*70}\n")

            for i, file in enumerate(files, 1):
                # 更新进度条
                progress_value = (i - 1) / total_files
                file_name = Path(file.name).name
                progress(progress_value, desc=f"📄 正在处理 ({i}/{total_files}): {file_name[:30]}...")

                try:
                    file_path = file.name
                    print(f"\n{'='*70}")
                    print(f"📄 [{i}/{total_files}] 正在处理: {file_name}")
                    print(f"{'='*70}")

                    summary_data = summarizer.summarize_paper(
                        file_path,
                        custom_prompt if custom_prompt else None
                    )

                    # 验证总结内容
                    if not summary_data.get('summary') or len(summary_data['summary'].strip()) < 50:
                        raise Exception("生成的总结内容为空或太短")

                    summaries.append(summary_data)
                    success_count = sum(1 for s in summaries if not s['summary'].startswith('❌'))
                    print(f"\n✅ {file_name} 处理成功！")
                    print(f"📊 进度: 已完成 {i}/{total_files} 篇 (成功: {success_count}, 失败: {i - success_count})")

                except Exception as e:
                    error_msg = f"❌ 处理失败: {str(e)}"
                    print(f"\n{error_msg}")
                    print(f"文件路径: {file.name}")
                    summaries.append({
                        "file_name": Path(file.name).name,
                        "summary": error_msg,
                        "file_path": file.name
                    })
                    success_count = sum(1 for s in summaries if not s['summary'].startswith('❌'))
                    print(f"📊 进度: 已完成 {i}/{total_files} 篇 (成功: {success_count}, 失败: {i - success_count})")

            # 完成进度
            progress(1.0, desc="✅ 处理完成！")

            # 统计处理结果
            success_count = sum(1 for s in summaries if not s['summary'].startswith('❌'))
            fail_count = total_files - success_count

            print(f"\n{'='*70}")
            print(f"🎉 批量处理完成！")
            print(f"📊 总计: {total_files} 篇 | ✅ 成功: {success_count} 篇 | ❌ 失败: {fail_count} 篇")
            print(f"{'='*70}\n")

            # 生成Markdown内容
            markdown_content = self.generate_markdown(summaries)

            # 保存到文件
            output_file = f"summaries/summaries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            status_msg = f"✅ 成功处理 {len(summaries)} 篇论文\n📄 结果已保存到: {output_file}"

            return markdown_content, output_file, status_msg

        except Exception as e:
            return "", None, f"❌ 错误: {str(e)}"

    def generate_markdown(self, summaries):
        """生成Markdown格式的总结"""
        md_content = "# 📚 论文总结合集\n\n"
        md_content += f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        md_content += f"**论文数量**: {len(summaries)}\n\n"
        md_content += "---\n\n"

        for i, summary_data in enumerate(summaries, 1):
            md_content += f"## 📄 {i}. {summary_data['file_name']}\n\n"
            md_content += f"{summary_data['summary']}\n\n"
            md_content += "---\n\n"

        return md_content

    def get_default_prompt(self):
        """获取默认prompt"""
        return """请按照实证研究论文的结构，对以下论文进行详细总结：

## 1. 论文基本信息
- 标题和作者（如果能识别）
- 研究问题/研究假设

## 2. 研究背景与理论基础
- 研究背景和动机
- 文献回顾与理论框架
- 研究贡献和创新点

## 3. 研究方法
- 样本来源和数据说明
- 变量定义（因变量、自变量、控制变量）
- 研究设计和模型设定
- 实证方法（如回归模型、DID、PSM等）

## 4. 实证结果
- 描述性统计
- 基准回归结果
- 稳健性检验（如果有）
- 机制分析或异质性分析（如果有）

## 5. 结论与启示
- 主要研究发现
- 理论贡献和实践意义
- 政策建议
- 研究局限性和未来研究方向

请用中文总结，条理清晰，重点突出实证研究的核心要素。

论文内容：
{content}"""

    def get_provider_config(self, provider):
        """
        根据提供商返回推荐的配置

        Args:
            provider: API提供商名称

        Returns:
            包含base_url和model推荐值的字典
        """
        configs = {
            'OpenAI': {
                'base_url': 'https://api.openai.com/v1',
                'model': 'gpt-4o',
                'base_url_placeholder': 'https://api.openai.com/v1（可选）',
                'model_placeholder': 'gpt-4o, gpt-4o-mini, gpt-4-turbo, gpt-3.5-turbo'
            },
            'Gemini': {
                'base_url': '',
                'model': 'gemini-2.5-flash',
                'base_url_placeholder': '例如: https://your-api-url/v1（必填）',
                'model_placeholder': 'gemini-2.5-flash, gemini-2.0-flash-exp, gemini-1.5-pro'
            },
            'Claude': {
                'base_url': '',
                'model': 'claude-3-sonnet',
                'base_url_placeholder': '例如: https://your-api-url/v1（必填）',
                'model_placeholder': 'claude-3-sonnet, claude-3-opus'
            },
            '自定义': {
                'base_url': '',
                'model': '',
                'base_url_placeholder': '输入自定义API地址',
                'model_placeholder': '输入模型名称'
            }
        }
        return configs.get(provider, configs['自定义'])

    def create_interface(self):
        """创建Gradio界面"""

        # 自定义CSS - 保存为实例变量供launch()使用
        self.custom_css = """
        .gradio-container {
            font-family: 'Microsoft YaHei', sans-serif;
        }
        .main-title {
            text-align: center;
            color: #2c3e50;
            margin-bottom: 20px;
        }
        """

        with gr.Blocks(title="PDF论文总结工具") as app:
            gr.Markdown(
                """
                # 📚 PDF论文总结工具

                使用OpenAI API自动总结PDF格式的学术论文，支持批量处理和自定义prompt。
                """,
                elem_classes="main-title"
            )

            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ⚙️ API配置")

                    provider_dropdown = gr.Dropdown(
                        label="API提供商",
                        choices=['OpenAI', 'Gemini', 'Claude', '自定义'],
                        value=self.saved_provider,
                        interactive=True
                    )

                    api_key_input = gr.Textbox(
                        label="API密钥",
                        placeholder="输入你的API密钥",
                        type="password",
                        value=self.saved_api_key
                    )

                    base_url_input = gr.Textbox(
                        label="API基础URL",
                        placeholder=self.get_provider_config(self.saved_provider)['base_url_placeholder'],
                        value=self.saved_base_url
                    )

                    model_input = gr.Textbox(
                        label="模型名称",
                        placeholder=self.get_provider_config(self.saved_provider)['model_placeholder'],
                        value=self.saved_model
                    )

                    save_config = gr.Checkbox(
                        label="处理PDF时自动保存配置",
                        value=True
                    )

                    # 添加独立的保存配置按钮
                    with gr.Row():
                        save_config_btn = gr.Button("💾 立即保存配置", size="sm", variant="secondary")
                        config_status = gr.Textbox(label="", placeholder="配置状态", lines=1, show_label=False, interactive=False)

                    gr.Markdown("### 📝 自定义Prompt")

                    custom_prompt_input = gr.Textbox(
                        label="自定义Prompt模板",
                        placeholder="使用 {content} 作为论文内容的占位符",
                        lines=8,
                        value=self.saved_prompt if self.saved_prompt else self.get_default_prompt()
                    )

                    with gr.Row():
                        reset_prompt_btn = gr.Button("🔄 恢复默认Prompt", size="sm")
                        reset_prompt_btn.click(
                            fn=lambda: self.get_default_prompt(),
                            outputs=custom_prompt_input
                        )

                with gr.Column(scale=2):
                    gr.Markdown("### 📂 上传PDF文件")

                    file_input = gr.File(
                        label="选择PDF文件（可多选）",
                        file_count="multiple",
                        file_types=[".pdf"]
                    )

                    process_btn = gr.Button("🚀 开始总结", variant="primary", size="lg")

                    status_output = gr.Textbox(
                        label="状态信息",
                        lines=2,
                        interactive=False
                    )

                    download_file = gr.File(
                        label="📥 下载Markdown文件",
                        visible=True
                    )

                    gr.Markdown("### 📄 总结结果")

                    markdown_output = gr.Markdown(
                        label="总结内容",
                        value="等待处理..."
                    )

            # 定义提供商改变时的处理函数
            def update_provider_config(provider):
                """当提供商改变时，更新配置字段的提示和默认值"""
                config = self.get_provider_config(provider)
                return [
                    gr.update(placeholder=config['base_url_placeholder']),
                    gr.update(placeholder=config['model_placeholder'], value=config['model'])
                ]

            # 绑定提供商改变事件
            provider_dropdown.change(
                fn=update_provider_config,
                inputs=[provider_dropdown],
                outputs=[base_url_input, model_input]
            )

            # 绑定保存配置按钮
            save_config_btn.click(
                fn=self.save_config_only,
                inputs=[
                    provider_dropdown,
                    api_key_input,
                    base_url_input,
                    model_input,
                    custom_prompt_input
                ],
                outputs=[config_status]
            )

            # 绑定处理函数
            process_btn.click(
                fn=self.process_papers,
                inputs=[
                    file_input,
                    provider_dropdown,
                    api_key_input,
                    base_url_input,
                    model_input,
                    custom_prompt_input,
                    save_config
                ],
                outputs=[markdown_output, download_file, status_output]
            )

            # 添加说明
            gr.Markdown(
                """
                ---
                ### 💡 使用说明

                1. **选择API提供商**: 从下拉菜单中选择 OpenAI、Gemini 或其他提供商
                2. **配置API**:
                   - **API密钥**: 输入你的 API 密钥
                   - **API基础URL**: 对于 Gemini，填入 new_api 转换后的地址（如 `https://your-api.com/v1`）
                   - **模型名称**: 会根据选择的提供商自动推荐，也可自定义
                3. **自定义Prompt**: 可以修改 prompt 模板来定制总结的格式和内容
                4. **上传PDF**: 选择一个或多个 PDF 论文文件
                5. **开始总结**: 点击按钮开始处理，结果会显示在下方并自动保存到文件

                **提示**:
                - 支持 OpenAI、Gemini（通过 new_api 转换）、Claude 等多种 API
                - 对于 Gemini，请填写完整的 API 地址和密钥
                - 勾选"保存配置"可以在下次启动时自动加载配置
                - 生成的 Markdown 文件会保存在当前目录，文件名包含时间戳
                - Prompt 模板中使用 `{content}` 作为论文内容的占位符
                """
            )

        return app


def main():
    """启动应用"""
    app_instance = PaperSummarizerApp()
    app = app_instance.create_interface()

    # 启动应用 - 优化远程服务器配置
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True,
        # 增加连接稳定性配置
        max_threads=10,  # 最大并发线程
        quiet=False,  # 显示日志便于调试
        # 允许跨域（如果需要通过反向代理访问）
        allowed_paths=["/app/summaries"],
        # Gradio 6.0: css参数已移至launch()
        css=app_instance.custom_css
    )


if __name__ == "__main__":
    main()
