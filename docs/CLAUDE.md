# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A PDF paper summarization tool that uses OpenAI-compatible APIs to automatically generate summaries of academic papers. The tool provides both a FastAPI web interface and a command-line interface for batch processing.

## Running the Application

### Setup (Virtual Environment Recommended)

```bash
# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt
```

### Web Interface (Primary Usage)

```bash
python app_fastapi.py
```

Launches FastAPI interface on `http://localhost:7860`

### Command Line Interface

```bash
python paper_summarizer.py --folder ./papers --output summaries.md
```

Required environment variable or CLI argument: `OPENAI_API_KEY`

### Docker Deployment

```bash
docker-compose up -d
```

Access at `http://localhost:18860`

## Architecture

### Two-Component Design

1. **`paper_summarizer.py`** - Core logic module
   - `PaperSummarizer` class: Handles PDF text extraction and API communication
   - Stateless processing: Each paper is processed independently
   - Error handling: Individual paper failures don't stop batch processing
   - Content truncation: Limits text to 16000 characters before API call to avoid token limits

2. **`app_fastapi.py`** - FastAPI web interface (lightweight, ~100MB memory)
   - Pure HTML/JS frontend embedded in Python
   - Configuration persistence: Saves/loads from `data/config.json`
   - Low resource usage compared to previous Gradio version (~2GB)
   - Auto-saves output: Creates timestamped `summaries_YYYYMMDD_HHMMSS.md` files

### Key Design Patterns

- **Configuration precedence**: Web UI > `config.json` > environment variables > CLI arguments
- **Prompt templating**: All prompts must contain `{content}` placeholder for paper text injection
- **API abstraction**: Supports any OpenAI-compatible API via `base_url` parameter (OpenAI, Gemini, Claude)
- **Graceful degradation**: Failed papers generate error entries in output rather than stopping the batch

## Configuration

### API Configuration Methods

1. Environment variable: `API_KEY`, `BASE_URL`, `MODEL`
2. Config file: `data/config.json` (auto-created by web UI)
3. CLI arguments: `--api-key`, `--base-url`, `--model`
4. Web UI inputs (priority over all others)

### Custom Prompts

- Template files can be passed via `--prompt` CLI arg
- Web UI provides editable prompt textarea
- Must include `{content}` placeholder
- Default prompt in `paper_summarizer.py`

## Important Constraints

- **Text extraction**: Only works with text-based PDFs (not scanned images)
- **Token limit**: Content truncated to 16000 chars in `summarize_text()`
- **API parameters**: Hard-coded `temperature=0.7` and `max_tokens=4000`
- **Batch size**: Recommend max 10-20 papers per batch to avoid rate limits

## File Outputs

- Output markdown files follow pattern: `summaries_YYYYMMDD_HHMMSS.md`
- Format: Header with metadata, then numbered sections per paper
- Includes both successful summaries and error messages for failed papers

## Modifying Behavior

When users want to change:

- **Summary style**: Edit prompt template (preserve `{content}` placeholder)
- **API settings**: Modify data/config.json or web UI inputs
- **Token/temperature**: Edit `paper_summarizer.py` (requires code change)
- **Content length**: Edit truncation limit in `paper_summarizer.py`
- **Output format**: Modify `generate_markdown()` in app_fastapi.py

## Dependencies

Core: `PyPDF2` (text extraction), `openai>=1.0.0` (API client), `fastapi` + `uvicorn` (web UI)

Install: `pip install -r requirements.txt`

## Docker Multi-Platform Build

GitHub Actions automatically builds and pushes multi-platform images:

- `linux/amd64`
- `linux/arm64`

Image: `ghcr.io/jtwang980611/paper-summerizer:latest`
