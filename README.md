# 📚 PDF论文总结工具

一个基于OpenAI API的PDF论文自动总结工具，支持批量处理、自定义Prompt和可视化Web界面。

## ✨ 特性

- 📄 **批量处理**: 支持同时处理多个PDF文件
- 🤖 **多AI支持**: 支持 OpenAI、Gemini、Claude 等多种AI API
- 🎨 **轻量Web界面**: 基于FastAPI的低内存占用Web界面（~100MB vs Gradio的~2GB）
- 🔧 **自定义Prompt**: 灵活定制总结的格式和内容
- 💾 **配置保存**: 支持保存API配置、提供商选择和Prompt模板
- 🌐 **API兼容**: 支持所有兼容OpenAI格式的API（通过new_api等转换工具）
- 📝 **Markdown输出**: 自动生成格式化的Markdown文件
- 🐳 **多平台支持**: Docker镜像支持 amd64 和 arm64 架构

## 🚀 快速开始

### Docker 一键部署（推荐）

```bash
docker run -d -p 7860:7860 --name paper-summerizer ghcr.io/jtwang980611/paper-summerizer:latest
```

访问 `http://localhost:7860`，在 Web 界面中配置 API 密钥即可使用。

---

## 📦 其他部署方式

> 💡 **部署指南**：
>
> - 🐳 Docker 详细配置：查看 [Docker 部署指南](docs/DOCKER.md)
> - 🚀 服务器部署：查看 [服务器部署指南](docs/SERVER_DEPLOYMENT.md)
> - 📘 GitHub 部署：查看 [GitHub 上传和部署指南](docs/GITHUB_GUIDE.md)

### 方式一：Docker Compose

```bash
git clone https://github.com/jtwang980611/paper-summerizer.git
cd paper-summerizer
docker-compose up -d
```

访问 `http://localhost:18860`

### 方式二：本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 启动应用
python app_fastapi.py
```

访问 `http://localhost:7860`

### 方式三：命令行

```bash
python paper_summarizer.py \
  --folder ./papers \
  --output summaries.md \
  --api-key sk-your-api-key \
  --model gpt-3.5-turbo
```

**命令行参数说明：**

- `--folder`: PDF文件所在文件夹路径（必需）
- `--output`: 输出Markdown文件路径（默认：summaries.md）
- `--api-key`: OpenAI API密钥（或从环境变量读取）
- `--base-url`: API基础URL（可选）
- `--model`: 使用的模型名称（默认：gpt-3.5-turbo）
- `--prompt`: 自定义Prompt文件路径（可选）

### 使用自定义Prompt

你可以创建自己的Prompt模板文件（参考 `config/prompt_template.txt`），在模板中使用 `{content}` 作为论文内容的占位符：

```bash
python paper_summarizer.py \
  --folder ./papers \
  --prompt my_custom_prompt.txt
```

## 📁 项目结构

```
paper-summerizer/
├── README.md                 # 项目说明文档
├── app_fastapi.py            # FastAPI Web应用（主入口）
├── paper_summarizer.py       # 核心处理逻辑
├── requirements.txt          # Python依赖
├── .gitignore               # Git忽略规则
│
├── 🐳 Dockerfile             # Docker镜像配置
├── 🐳 docker-compose.yml     # Docker Compose配置
├── 🐳 .dockerignore          # Docker忽略规则
│
├── .github/workflows/        # GitHub Actions
│   └── docker-publish.yml   # 多平台镜像构建
│
├── docs/                     # 📁 文档目录
│   ├── QUICKSTART.md        # 快速开始指南
│   ├── GITHUB_GUIDE.md      # GitHub 上传和部署指南
│   ├── DOCKER.md            # Docker 部署指南
│   ├── SERVER_DEPLOYMENT.md # 服务器部署指南
│   └── CLAUDE.md            # Claude Code 使用说明
│
├── config/                   # 📁 配置文件目录
│   ├── config.example.json  # 配置文件示例
│   └── prompt_template.txt  # Prompt模板示例
│
├── summaries/                # 📁 生成的摘要目录（Docker挂载）
└── data/                     # 📁 配置数据目录
```

## 🔧 配置说明

### API配置

支持多种AI提供商，在Web界面中选择提供商后，系统会自动提示相应的配置：

1. **OpenAI**

   ```json
   {
     "provider": "OpenAI",
     "api_key": "sk-...",
     "base_url": "https://api.openai.com/v1",
     "model": "gpt-3.5-turbo"
   }
   ```
2. **Gemini（通过new_api）**

   ```json
   {
     "provider": "Gemini",
     "api_key": "your-gemini-key",
     "base_url": "https://your-new-api-url/v1",
     "model": "gemini-pro"
   }
   ```
3. **Claude（通过new_api）**

   ```json
   {
     "provider": "Claude",
     "api_key": "your-claude-key",
     "base_url": "https://your-api-url/v1",
     "model": "claude-3-sonnet"
   }
   ```
4. **自定义API**

   - 支持任何兼容OpenAI格式的API
   - 在界面中选择"自定义"并填入相应配置

### Prompt模板

Prompt模板必须包含 `{content}` 占位符，例如：

```
请总结以下论文的主要内容：

{content}

要求：
1. 用中文总结
2. 包含研究背景、方法、结果和结论
3. 字数控制在500字以内
```

## 💡 使用提示

1. **PDF质量**: 确保PDF文件是可提取文本的（非扫描版）
2. **文件大小**: 大文件会被截取前16000字符以避免超出token限制
3. **API费用**: 使用前请了解API的计费规则
4. **批量处理**: 建议每次处理10篇以内的论文
5. **错误处理**: 单个文件失败不会影响其他文件的处理

## 📊 输出示例

生成的Markdown文件格式：

```markdown
# 📚 论文总结合集

**生成时间**: 2024-01-01 12:00:00

**论文数量**: 3

---

## 📄 1. paper1.pdf

[总结内容...]

---

## 📄 2. paper2.pdf

[总结内容...]

---
```

## ⚠️ 注意事项

1. **API密钥安全**:

   - 不要将包含真实API密钥的配置文件提交到Git
   - 已在 `.gitignore` 中排除 `config.json` 和 `.env`
2. **PDF文件限制**:

   - 仅支持文本型PDF，不支持纯图片扫描版
   - 建议单个文件不超过50页
3. **网络要求**:

   - 需要稳定的网络连接访问API
   - 如遇连接问题，请检查代理设置

## 🛠️ 常见问题

**Q: 如何使用代理？**

A: 设置环境变量：

```bash
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

**Q: 如何更换模型？**

A: 在配置中修改 `model` 字段，支持的模型包括：

- gpt-3.5-turbo (更快、更便宜)
- gpt-4 (更强大、更准确)
- gemini-2.5-flash (Gemini)
- 其他兼容模型

**Q: 总结质量不满意怎么办？**

A: 尝试：

1. 调整Prompt模板，提供更详细的要求
2. 使用更强大的模型（如GPT-4）
3. 增加temperature参数以获得更多样化的输出

**Q: 如何处理大量论文？**

A: 建议分批处理，每批10-20篇，避免：

- API rate limit
- 网络超时
- 费用过高

## 📝 许可证

本项目仅供学习和研究使用。

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📮 联系方式

如有问题或建议，请通过Issue联系。

---

**Enjoy summarizing papers! 📚✨**
