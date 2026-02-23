# SRT Translator

Translate SRT subtitle files using AI (Alibaba Cloud, SiliconFlow & OpenRouter).

## Features

- Multiple provider support with automatic fallback
- Extracts subtitle text and translates
- Chunked processing for large files
- Configurable source/target languages

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
  - name: alibaba
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3-8b
    enabled: true
    proxy: null
    context_window: 32000    # Model's context window from docs
    extra_params:
      enable_thinking: false
      
  - name: siliconflow
    base_url: https://api.siliconflow.cn/v1
    model: Qwen/Qwen3-8B
    enabled: true
    context_window: 32000
    
  - name: openrouter
    base_url: https://openrouter.ai/api/v1
    model: qwen/qwen3-8b
    enabled: true
    context_window: 32000

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

| Parameter | Description | Formula/Value |
|-----------|-------------|---------------|
| `context_window` | Model's context window from documentation | e.g., 32000 for qwen3-8b |
| Chunk size | Max input chars per API call | `context_window × 0.75 × 0.5 × 1.5` |
| Safety margin | Reserve for prompt overhead | 0.75 (25% reserved) |
| Output reserve | Portion for translation output | 0.5 (50% for output) |
| Chars per token | Chinese text estimate | 1.5 chars/token |

**Example calculation** for 32k context:
- Input limit = 32000 × 0.75 × 0.5 × 1.5 = **18000 chars**

## API Keys

| Provider | Key Name | Get Key |
|----------|----------|---------|
| Alibaba Cloud | `ALIBABA_API_KEY` | https://dashscope.console.aliyun.com |
| SiliconFlow | `SILICONFLOW_API_KEY` | https://cloud.siliconflow.cn |
| OpenRouter | `OPENROUTER_API_KEY` | https://openrouter.ai/keys |

## Output

- Input: `input/video.srt`
- Output: `output/video.txt` (translated text)

## Architecture Notes

Inherited from srt-processor:

1. **Context window config** - Use `context_window` from model docs (single source of truth)
2. **Dynamic chunk sizing** - Calculated: `context_window × 0.75 × 0.5 × 1.5`
3. **No max_tokens in API** - Let provider use default output limit
4. **Translation validation** - Detects untranslated blocks (Chinese char ratio < 30%)
5. **Chunked processing** - Large files split at sentence boundaries
6. **Provider fallback** - Tries providers in config order
