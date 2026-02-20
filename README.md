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
    max_tokens: 8000
    extra_params:
      enable_thinking: false
      
  - name: siliconflow
    base_url: https://api.siliconflow.cn/v1
    model: Qwen/Qwen3-8B
    enabled: true
    max_tokens: 16000
    
  - name: openrouter
    base_url: https://openrouter.ai/api/v1
    model: qwen/qwen3-8b
    enabled: true
    max_tokens: 16000

processing:
  source_language: auto
  target_language: Chinese
  
rate_limit:
  requests_per_minute: 30
  max_retries: 3
  retry_delay: 5
  timeout: 120
```

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

1. **Per-provider max_tokens** - Alibaba limited to 8000, others can use 16000
2. **Chunked processing** - Large files split at sentence boundaries
3. **Connection pool management** - Shared httpx client with limits
4. **Proxy bypass** - Set `proxy: null` to skip system proxy
5. **Provider fallback** - Tries providers in config order
6. **Explicit cleanup** - Ensures connections closed on exit
