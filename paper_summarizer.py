import os
import json
import base64
import time
import random
from pathlib import Path
from typing import List, Dict
import PyPDF2
from openai import OpenAI
import requests


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
    retryable_status_codes: tuple = (429, 500, 502, 503, 504),
):
    """
    指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        retryable_exceptions: 可重试的异常类型
        retryable_status_codes: 可重试的HTTP状态码
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            num_retries = 0
            delay = base_delay

            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e).lower()

                    # 检查是否为速率限制错误
                    is_rate_limit = (
                        'rate limit' in error_msg or
                        'rate_limit' in error_msg or
                        '429' in error_msg or
                        'too many requests' in error_msg or
                        'quota' in error_msg
                    )

                    # 检查是否为可重试的服务器错误
                    is_server_error = any(str(code) in error_msg for code in retryable_status_codes)

                    # 检查是否为超时错误
                    is_timeout = 'timeout' in error_msg or 'timed out' in error_msg

                    should_retry = is_rate_limit or is_server_error or is_timeout

                    if not should_retry or num_retries >= max_retries:
                        raise

                    num_retries += 1

                    # 计算延迟时间
                    delay = min(delay * exponential_base, max_delay)

                    # 添加随机抖动，避免多个请求同时重试
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    # 速率限制错误使用更长的延迟
                    if is_rate_limit:
                        delay = max(delay, 10.0)  # 至少等待10秒

                    print(f"⚠️ 请求失败，{delay:.1f}秒后进行第 {num_retries}/{max_retries} 次重试...")
                    print(f"   错误信息: {str(e)[:100]}")
                    time.sleep(delay)

        return wrapper
    return decorator


class PaperSummarizer:
    """论文总结器 - 使用OpenAI API总结PDF论文"""

    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-3.5-turbo", rpm: int = None):
        """
        初始化论文总结器

        Args:
            api_key: OpenAI API密钥
            base_url: API基础URL（支持兼容OpenAI格式的API）
            model: 使用的模型名称
            rpm: 每分钟最大请求数（Rate Per Minute），用于速率限制
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.rpm = rpm
        self.last_request_time = 0  # 上次请求时间戳

        # 检测是否使用Gemini模型
        self.is_gemini = self._is_gemini_model(model)

        # 初始化客户端
        if base_url:
            self.client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = OpenAI(api_key=api_key)

        # 如果是Gemini模型且有base_url，使用Gemini原生格式（通过new-api）
        if self.is_gemini and base_url:
            print(f"✨ 检测到Gemini模型，将使用原生格式直接读取PDF")

    def _is_gemini_model(self, model: str) -> bool:
        """检测是否为Gemini模型"""
        return model.lower().startswith('gemini')

    def _wait_for_rate_limit(self):
        """根据RPM设置等待，确保不超过速率限制"""
        if not self.rpm or self.rpm <= 0:
            return

        min_interval = 60.0 / self.rpm  # 每次请求的最小间隔（秒）
        elapsed = time.time() - self.last_request_time

        if elapsed < min_interval:
            wait_time = min_interval - elapsed
            print(f"⏳ 速率限制: 等待 {wait_time:.1f} 秒 (RPM={self.rpm})")
            time.sleep(wait_time)

        self.last_request_time = time.time()

    @property
    def default_prompt(self):
        """默认的总结prompt（针对实证研究论文）"""
        return """请按照实证研究论文的结构，对以下论文进行详细总结：

## 1. 论文基本信息
- 标题，作者和年份（如果能识别）
- 研究问题/研究假设

## 2. 研究背景与理论基础
- 研究背景和动机
- 文献回顾与理论框架
- 研究贡献和创新点

## 3. 研究方法
- 样本来源和数据说明
- 变量定义（因变量、自变量、控制变量）
- 研究设计和模型设定

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

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        从PDF文件中提取文本

        Args:
            pdf_path: PDF文件路径

        Returns:
            提取的文本内容
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""

                # 提取所有页面的文本
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text()

                # 验证提取的文本
                if not text or len(text.strip()) < 100:
                    raise Exception(f"PDF文本提取失败或内容太少（提取到 {len(text)} 字符）")

                print(f"✅ 成功提取 {len(text)} 字符，共 {len(pdf_reader.pages)} 页")

                # 显示提取内容的前100个字符预览
                preview = text.strip()[:100].replace('\n', ' ')
                print(f"📝 内容预览: {preview}...")

                return text
        except Exception as e:
            raise Exception(f"PDF文本提取失败: {str(e)}")

    @retry_with_exponential_backoff(max_retries=3, base_delay=2.0)
    def summarize_text(self, text: str, custom_prompt: str = None) -> str:
        """
        使用OpenAI API总结文本

        Args:
            text: 要总结的文本
            custom_prompt: 自定义的prompt模板

        Returns:
            总结后的文本
        """
        try:
            # 速率限制等待
            self._wait_for_rate_limit()

            # 使用自定义prompt或默认prompt
            prompt_template = custom_prompt if custom_prompt else self.default_prompt
            prompt = prompt_template.format(content=text[:16000])  # 增加输入长度限制

            print(f"🔄 准备调用API...")
            print(f"   模型: {self.model}")
            print(f"   输入长度: {len(prompt)} 字符")

            # 调用OpenAI API
            print(f"⏳ 正在调用API生成总结，请稍候...")
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的学术论文分析助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000  # 增加输出token限制
            )

            # 验证响应
            if not response.choices or len(response.choices) == 0:
                raise Exception("API返回为空，没有生成任何内容")

            summary = response.choices[0].message.content

            if not summary or len(summary.strip()) < 50:
                raise Exception(f"API返回内容太少或为空（长度: {len(summary) if summary else 0}）")

            print(f"✅ API调用成功，生成总结长度: {len(summary)} 字符")

            # 显示总结内容的前100个字符预览
            summary_preview = summary.strip()[:100].replace('\n', ' ')
            print(f"📄 总结预览: {summary_preview}...")

            return summary

        except Exception as e:
            print(f"❌ API调用错误详情: {str(e)}")
            raise Exception(f"API调用失败: {str(e)}")

    def summarize_paper(self, pdf_path: str, custom_prompt: str = None) -> Dict:
        """
        总结单篇论文

        Args:
            pdf_path: PDF文件路径
            custom_prompt: 自定义prompt

        Returns:
            包含文件名和总结的字典
        """
        file_name = Path(pdf_path).name
        print(f"正在处理: {file_name}")

        if self.is_gemini and self.base_url:
            # Gemini模式（通过new-api）：使用原生格式直接读取PDF
            summary = self.summarize_pdf_with_gemini_native(pdf_path, custom_prompt)
        else:
            # 其他模式：提取文本后总结
            text = self.extract_text_from_pdf(pdf_path)
            summary = self.summarize_text(text, custom_prompt)

        return {
            "file_name": file_name,
            "summary": summary,
            "file_path": pdf_path
        }

    @retry_with_exponential_backoff(max_retries=3, base_delay=2.0)
    def summarize_pdf_with_gemini_native(self, pdf_path: str, custom_prompt: str = None) -> str:
        """
        使用Gemini原生格式（通过new-api）直接读取并总结PDF

        Args:
            pdf_path: PDF文件路径
            custom_prompt: 自定义prompt

        Returns:
            总结后的文本
        """
        try:
            # 速率限制等待
            self._wait_for_rate_limit()

            print(f"📄 使用Gemini原生格式直接读取PDF文件...")

            # 读取PDF文件并进行base64编码
            with open(pdf_path, 'rb') as pdf_file:
                pdf_data = pdf_file.read()
                pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')

            print(f"✅ PDF文件读取成功，大小: {len(pdf_data)} 字节")

            # 准备prompt
            prompt_template = custom_prompt if custom_prompt else self.default_prompt
            # Gemini直接读取PDF，移除{content}占位符
            if '{content}' in prompt_template:
                prompt_text = prompt_template.replace('{content}', '请分析上传的PDF文件。')
            else:
                prompt_text = prompt_template

            # 构建Gemini原生格式请求URL
            # 移除base_url末尾的斜杠和/v1路径
            base = self.base_url.rstrip('/')
            if base.endswith('/v1'):
                base = base[:-3]

            url = f"{base}/v1beta/models/{self.model}:generateContent?key={self.api_key}"

            print(f"🔄 准备调用Gemini API...")
            print(f"   模型: {self.model}")
            print(f"   端点: {url[:100]}...")
            headers = {
                'Content-Type': 'application/json'
            }

            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt_text},
                        {
                            "inline_data": {
                                "mime_type": "application/pdf",
                                "data": pdf_base64
                            }
                        }
                    ]
                }]
            }

            # 调用Gemini API
            print(f"⏳ 正在调用API生成总结，请稍候...")
            response = requests.post(url, headers=headers, json=payload, timeout=300)

            # 检查响应状态
            if response.status_code != 200:
                error_msg = f"API返回错误: {response.status_code} - {response.text}"
                raise Exception(error_msg)

            # 解析响应
            result = response.json()

            # 提取生成的文本
            if 'candidates' not in result or len(result['candidates']) == 0:
                raise Exception(f"API返回为空，没有生成任何内容: {result}")

            candidate = result['candidates'][0]
            if 'content' not in candidate or 'parts' not in candidate['content']:
                raise Exception(f"API返回格式异常: {result}")

            summary = candidate['content']['parts'][0].get('text', '')

            # 验证响应
            if not summary or len(summary.strip()) < 50:
                raise Exception(f"API返回内容太少或为空（长度: {len(summary)}）")

            print(f"✅ API调用成功，生成总结长度: {len(summary)} 字符")

            # 显示总结内容的前100个字符预览
            summary_preview = summary.strip()[:100].replace('\n', ' ')
            print(f"📄 总结预览: {summary_preview}...")

            return summary

        except requests.exceptions.Timeout:
            print(f"❌ API调用超时")
            raise Exception("API调用超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络请求错误: {str(e)}")
            raise Exception(f"网络请求失败: {str(e)}")
        except Exception as e:
            print(f"❌ Gemini API调用错误详情: {str(e)}")
            raise Exception(f"Gemini API调用失败: {str(e)}")

    def summarize_papers_in_folder(self, folder_path: str, custom_prompt: str = None, delay_between_requests: float = 2.0) -> List[Dict]:
        """
        总结文件夹中的所有PDF论文

        Args:
            folder_path: 包含PDF文件的文件夹路径
            custom_prompt: 自定义prompt
            delay_between_requests: 每次请求之间的延迟（秒），用于避免触发速率限制

        Returns:
            所有论文总结的列表
        """
        summaries = []
        pdf_files = list(Path(folder_path).glob("*.pdf"))

        if not pdf_files:
            raise Exception(f"在 {folder_path} 中未找到PDF文件")

        print(f"找到 {len(pdf_files)} 个PDF文件")

        for i, pdf_file in enumerate(pdf_files):
            try:
                summary_data = self.summarize_paper(str(pdf_file), custom_prompt)
                summaries.append(summary_data)
            except Exception as e:
                print(f"处理 {pdf_file.name} 时出错: {str(e)}")
                summaries.append({
                    "file_name": pdf_file.name,
                    "summary": f"处理失败: {str(e)}",
                    "file_path": str(pdf_file)
                })

            # 在处理下一个文件之前添加延迟，避免触发速率限制
            if i < len(pdf_files) - 1:
                print(f"⏳ 等待 {delay_between_requests} 秒后处理下一个文件...")
                time.sleep(delay_between_requests)

        return summaries

    def save_summaries_to_markdown(self, summaries: List[Dict], output_path: str):
        """
        将所有总结保存到Markdown文件

        Args:
            summaries: 论文总结列表
            output_path: 输出Markdown文件路径
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# 论文总结合集\n\n")
            f.write(f"生成时间: {Path(output_path).stat().st_mtime}\n\n")
            f.write(f"共 {len(summaries)} 篇论文\n\n")
            f.write("---\n\n")

            for i, summary_data in enumerate(summaries, 1):
                f.write(f"## {i}. {summary_data['file_name']}\n\n")
                f.write(f"**文件路径**: `{summary_data['file_path']}`\n\n")
                f.write(f"{summary_data['summary']}\n\n")
                f.write("---\n\n")

        print(f"总结已保存到: {output_path}")


def main():
    """命令行使用示例"""
    import argparse

    parser = argparse.ArgumentParser(description='PDF论文总结工具')
    parser.add_argument('--folder', type=str, required=True, help='包含PDF文件的文件夹路径')
    parser.add_argument('--output', type=str, default='summaries.md', help='输出Markdown文件路径')
    parser.add_argument('--api-key', type=str, help='OpenAI API密钥（或从环境变量读取）')
    parser.add_argument('--base-url', type=str, help='API基础URL（可选）')
    parser.add_argument('--model', type=str, default='gpt-3.5-turbo', help='使用的模型')
    parser.add_argument('--prompt', type=str, help='自定义prompt文件路径')

    args = parser.parse_args()

    # 获取API密钥
    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("错误: 请提供API密钥（通过--api-key参数或OPENAI_API_KEY环境变量）")
        return

    # 读取自定义prompt（如果提供）
    custom_prompt = None
    if args.prompt and os.path.exists(args.prompt):
        with open(args.prompt, 'r', encoding='utf-8') as f:
            custom_prompt = f.read()

    # 创建总结器
    summarizer = PaperSummarizer(
        api_key=api_key,
        base_url=args.base_url,
        model=args.model
    )

    # 处理论文
    summaries = summarizer.summarize_papers_in_folder(args.folder, custom_prompt)

    # 保存结果
    summarizer.save_summaries_to_markdown(summaries, args.output)
    print("完成!")


if __name__ == "__main__":
    main()
