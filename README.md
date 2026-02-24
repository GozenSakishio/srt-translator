# SRT Translator

Translate SRT subtitle files using AI (SiliconFlow & OpenRouter).

## Features

- Multiple provider support with automatic fallback
- Extracts subtitle text and translates
- Chunked processing for large files
- Configurable source/target languages
- Explicit block counting to prevent translation truncation

## Quick Start (Windows PowerShell)

```powershell
# 1. Clone
git clone https://github.com/GozenSakishio/translator
cd translator

# 2. Setup virtual environment
python3 -m venv .venv
.\.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API keys
Copy-Item .env.example .env
# Edit .env with your API keys

# 5. Translate
Copy-Item your\files\*.srt input\
python run.py
```

## CLI Options

```powershell
python run.py                      # Use all enabled providers
python run.py -p openrouter        # Use only openrouter
python run.py -s English -t Japanese  # Override languages
python run.py -l                   # List available providers
```

## Configuration

Edit `config.yaml`:

```yaml
providers:
  - name: siliconflow
    base_url: https://api.siliconflow.cn/v1
    model: Qwen/Qwen3-8B
    enabled: true
    proxy: null
    context_window: 32000
    max_output_tokens: 16000
    
  - name: openrouter
    base_url: https://openrouter.ai/api/v1
    model: qwen/qwen3-8b
    enabled: true
    context_window: 32000
    max_output_tokens: 16000

processing:
  source_language: auto
  target_language: Chinese
  
rate_limit:
  requests_per_minute: 30
  max_retries: 3
  retry_delay: 5
  timeout: 120
```

### Parameter Reference

| Parameter | Description | Value |
|-----------|-------------|-------|
| `context_window` | Model's context window | 32000 for qwen3-8b |
| `max_output_tokens` | API's max output limit | 16000 |
| Chunk size | Max input chars per API call | ~7920 chars |
| `max_tokens` (API) | Output token limit per request | ~14400 tokens |

**Chunk size formula:** `min(context × 0.75 × 0.33, output × 0.9 ÷ 2.67 × 4)`

## API Keys

| Provider | Key Name | Get Key |
|----------|----------|---------|
| SiliconFlow | `SILICONFLOW_API_KEY` | https://cloud.siliconflow.cn |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |

## Output

- Input: `input/video.srt`
- Output: `output/video.srt` (translated)

## Architecture Notes

1. **Context-based configuration** - Single source of truth from model docs
2. **Block-boundary splitting** - Chunks split at `[index]` boundaries
3. **Explicit block counting** - Prompt includes exact block count and last index to prevent truncation
4. **Translation validation** - Detects untranslated blocks (exact match or <15% Chinese chars)
5. **Provider fallback** - Tries providers in config order
