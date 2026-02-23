# SRT Translator - Learning Notes

## Overview

This document captures key learnings from building an SRT subtitle translator with AI providers.

---

## 1. SRT Format Preservation

### Problem
Original code extracted text only, losing timecodes and structure. Output was `.txt` not `.srt`.

### Solution
```python
def parse_srt(srt_content: str) -> list[dict]:
    # Parse into blocks with index, timestamp, text
    # Each block = {'index': 1, 'timestamp': '00:00:00,000 --> 00:00:04,340', 'text': ['Line 1']}

def blocks_to_translatable_text(blocks: list[dict]) -> str:
    # Format: "[1] First subtitle text\n[2] Second subtitle text"
    # Index markers [N] allow mapping translations back to original blocks

def build_srt(blocks: list[dict], translated_texts: list[str]) -> str:
    # Reconstruct SRT with original timestamps + translated text
```

### Key Insight
- Output `[N] text` format for translation, then parse back using index markers
- Original timestamps preserved throughout the process
- Output file extension must be `.srt` not `.txt`

---

## 2. Context-Aware Translation

### Problem
Generic translations don't use domain-appropriate terminology (e.g., "render" might translate incorrectly).

### Solution
Added configurable context field:

```yaml
processing:
  context: "Blender 3D software tutorial - technical terms include: render, shader, node, vertex, mesh, UV, texture, animation, keyframe"
  translation_style: natural  # or: literal, formal
```

```python
def build_prompt(prompt_template: str, raw_text: str, config: dict) -> str:
    context = config['processing'].get('context', 'General content')
    style = config['processing'].get('translation_style', 'natural')
    return prompt_template.format(
        source_language=source_lang,
        target_language=target_lang,
        context=context,
        style=style,
        content=raw_text
    )
```

### CLI Usage
```bash
python run.py -c "Houdini tutorial - SOP, DOP, VEX, procedural"
python run.py --style formal
```

---

## 3. Translation Validation

### Problem
AI sometimes returns untranslated text (returns English instead of Chinese).

### Solution
```python
def is_translated(text: str, target_lang: str) -> bool:
    if target_lang.lower() in ('chinese', 'zh', '中文'):
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        return chinese_chars > len(text) * 0.1  # >10% Chinese chars
    return bool(text.strip())

# In processing loop:
if not is_translated(result, target_lang):
    print(f"    Warning: Translation may be incomplete, retrying...")
    result, provider = process_with_fallback(providers, prompt, config)
```

---

## 4. Large Model Performance Reality

### Problem
Added `qwen3.5-plus` (larger model, 128k context) expecting better results, but it always timed out.

### Investigation Results

| Model | Context | Chunk Size | Time per Chunk | Status |
|-------|---------|------------|----------------|--------|
| qwen3-8b | 32k | 12k chars | ~30-60s | Works |
| qwen3.5-plus | 128k | 5k chars | ~75s for 2.5k | Timeout |

### Key Insight
**Context limit ≠ Processing speed**

Larger models can handle bigger context but process slower. The API response time scales non-linearly with input size for some models.

### Lesson Learned
> Over-engineering for "future flexibility" adds complexity without value. Test real-world performance before adding features.

### What We Removed
- `context_limit` per provider
- `max_chunk_size` config
- Per-provider timeout overrides
- `alibaba-plus` provider entirely

### Simple Solution
```python
DEFAULT_CHUNK_SIZE = 12000  # Works reliably for all providers
```

---

## 5. Chunking Strategy

### Why Chunking Matters
1. **API timeouts** - Large requests exceed reasonable timeout limits
2. **Reliability** - Failed chunks can be retried independently
3. **Rate limiting** - Processes can pause between chunks

### Implementation
```python
def split_text_into_chunks(text: str, max_size: int = 12000) -> list[str]:
    sentences = re.split(r'(?<=[。.!?])\s*', text)  # Split at sentence boundaries
    # Build chunks respecting max_size
    # Last chunk may be smaller
```

### Output
```
Split into 3 chunks ([11989, 11984, 3605] chars each, limit: 12000)
```

---

## 6. Provider Configuration

### Working Config
```yaml
providers:
  - name: alibaba
    base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
    model: qwen3-8b
    enabled: true
    max_tokens: 8000
    
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
```

### Fallback Order
Providers are tried in config order. If first fails, second is attempted, etc.

---

## 7. Key Files Structure

```
translator/
├── run.py                 # Main script
├── config.yaml            # Configuration
├── input/                 # Source SRT files
├── output/                # Translated SRT files
└── providers/
    ├── __init__.py        # Provider factory
    ├── base.py            # BaseProvider class
    ├── alibaba.py         # Alibaba/Qwen provider
    ├── siliconflow.py     # SiliconFlow provider
    └── openrouter.py      # OpenRouter provider
```

---

## 8. Common Pitfalls

### File Format
- Output must be `.srt` not `.txt`
- Must preserve original timestamps

### API Timeouts
- Per-provider timeout in config: `timeout: 180`
- Provider-specific timeout override: not recommended (removed)

### Translation Quality
- Use context for domain-specific terms
- Validate translations contain target language characters
- Retry failed/incomplete translations

### Model Selection
- Larger ≠ better for practical use
- Test real-world performance before committing
- Consider cost, speed, and reliability together

---

## 9. Final Architecture

```
Input SRT
    ↓
Parse into blocks (index, timestamp, text)
    ↓
Format with [N] markers
    ↓
Split into chunks (12k chars max)
    ↓
Translate via AI provider
    ↓
Validate translation
    ↓
Parse translated text using [N] markers
    ↓
Rebuild SRT with original timestamps
    ↓
Output SRT
```

---

## 10. Commands Reference

```bash
# Run with all enabled providers
python run.py

# Use specific provider
python run.py -p alibaba

# Override source/target language
python run.py -s English -t Chinese

# Set context for domain
python run.py -c "Houdini 3D software tutorial"

# Set translation style
python run.py --style formal

# List available providers
python run.py -l
```

---

## Summary

| Feature | Status | Complexity |
|---------|--------|------------|
| SRT format preservation | ✓ Kept | Low |
| Context-aware translation | ✓ Kept | Low |
| Translation validation | ✓ Kept | Medium |
| Translation style options | ✓ Kept | Low |
| Per-provider context_limit | ✗ Removed | High |
| max_chunk_size config | ✗ Removed | Medium |
| alibaba-plus provider | ✗ Removed | N/A |

**Core principle**: Simple, working solutions beat over-engineered flexibility. Test real-world performance before adding complexity.
