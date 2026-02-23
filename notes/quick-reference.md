# Quick Reference - SRT Translator

## Commands

```bash
python run.py                           # Run with all providers
python run.py -p alibaba                # Use specific provider
python run.py -c "Context here"         # Set translation context
python run.py --style formal            # Set translation style
python run.py -l                        # List providers
```

## Config Structure

```yaml
providers:
  - name: alibaba
    model: qwen3-8b
    enabled: true
    max_tokens: 8000

processing:
  source_language: auto
  target_language: Chinese
  context: "Domain-specific terms here"
  translation_style: natural

rate_limit:
  timeout: 180
  max_retries: 3
```

## Key Constants

- `DEFAULT_CHUNK_SIZE = 12000` chars
- Translation validated if >10% target language chars
- Output format: `.srt` (preserves original timestamps)

## Provider Performance

| Provider | Model | Speed | Reliability |
|----------|-------|-------|-------------|
| alibaba | qwen3-8b | Fast | Good |
| siliconflow | Qwen3-8B | Fast | Good |
| openrouter | qwen/qwen3-8b | Medium | Good |

## Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Output is .txt | Wrong extension | Use `.srt` in output path |
| Timecodes lost | Text-only extraction | Parse blocks, preserve timestamps |
| Timeout | Large chunk | Keep chunks ≤12k chars |
| Untranslated text | AI returned English | Validate + retry |

## Files

- `run.py` - Main script
- `config.yaml` - Configuration
- `providers/` - AI provider implementations
- `input/` - Source SRT files
- `output/` - Translated SRT files
