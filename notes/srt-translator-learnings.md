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

## 4. max_tokens vs context_limit (Critical Distinction)

### The Confusion
These two settings are often confused but serve completely different purposes:

| Setting | Controls | Direction | Who Sets It |
|---------|----------|-----------|-------------|
| `max_tokens` | OUTPUT size | Model → Response | API provider limit |
| `context_limit` | INPUT size | User → Model | Model architecture |

### Visual Explanation
```
INPUT (your text)                    OUTPUT (AI response)
     ↓                                    ↓
[context_limit chars max]  →  Model  →  [max_tokens tokens max]
     ↑                                    ↑
   32,000 chars                        8,000 tokens
   (what you CAN send)                 (what it CAN return)
```

### Why Different max_tokens for Same Model?
Different API providers may impose different limits:

```yaml
providers:
  - name: alibaba
    model: qwen3-8b
    max_tokens: 8000      # Alibaba API limits to 8192
    
  - name: siliconflow
    model: Qwen/Qwen3-8B  # Same model!
    max_tokens: 16000     # SiliconFlow allows more output
```

### What Happens If max_tokens is Too Small?
```
Input:  [1] First line... [500] Last line  (1000 blocks)
Output: [1] 第一行... [200] 最后一...  ← TRUNCATED at max_tokens!
```

The model STOPS generating mid-sentence, leaving you with incomplete translation.

### Chunking Strategy

**Wrong approach:**
```python
DEFAULT_CHUNK_SIZE = 12000  # Arbitrary, ignores model capability
```

**Correct approach:**
```python
SAFETY_MARGIN = 0.8  # Use 80% of context_limit

def get_effective_chunk_size(providers) -> int:
    min_context = min(p.context_limit for p in providers)
    return int(min_context * SAFETY_MARGIN)
```

**Configuration:**
```yaml
providers:
  - name: alibaba
    model: qwen3-8b
    max_tokens: 8000       # Output limit (API enforced)
    context_limit: 32000   # Input limit (model capability)
```

### Why Less Chunking = Better Translation?
1. **Context preservation**: AI sees entire file context
2. **Natural flow**: Sentences and references stay connected  
3. **Fewer API calls**: Faster, cheaper, more reliable

### Example
| File Size | Old (12k chunks) | New (25.6k chunks) |
|-----------|------------------|-------------------|
| 30k chars | 3 chunks | 2 chunks |
| 50k chars | 5 chunks | 2 chunks |

---

## 5. Translation Validation

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

## 6. Large Model Performance (qwen3.5-plus Lesson)

### Problem
Added `qwen3.5-plus` (larger model, 128k context) expecting better results, but it always timed out.

### Investigation Results

| Model | Context | Chunk Size | Time per Chunk | Status |
|-------|---------|------------|----------------|--------|
| qwen3-8b | 32k | 25k chars | ~30-60s | Works |
| qwen3.5-plus | 128k | 2.5k chars | ~75s | Timeout |

### Key Insight
**Context limit ≠ Processing speed**

Larger models can handle bigger context but process slower. The API response time scales non-linearly with input size for some models.

### Lesson Learned
> Larger context window doesn't mean faster processing. Test real-world performance.

---

## 7. Provider Configuration

### Working Config
```yaml
providers:
  - name: alibaba
    model: qwen3-8b
    enabled: true
    max_tokens: 8000       # Output limit (API enforced)
    context_limit: 32000   # Input limit (model capability)
    
  - name: siliconflow
    model: Qwen/Qwen3-8B
    enabled: true
    max_tokens: 16000
    context_limit: 32000
    
  - name: openrouter
    model: qwen/qwen3-8b
    enabled: true
    max_tokens: 16000
    context_limit: 32000
```

### Fallback Order
Providers are tried in config order. If first fails, second is attempted, etc.

---

## 8. Key Files Structure

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

## 9. Common Pitfalls

### max_tokens vs context_limit
- `max_tokens` = OUTPUT limit (API enforced)
- `context_limit` = INPUT limit (model capability)

### File Format
- Output must be `.srt` not `.txt`
- Must preserve original timestamps

### API Timeouts
- Per-provider timeout in config: `timeout: 180`
- Larger chunks take longer - tune context_limit accordingly

### Translation Quality
- Use context for domain-specific terms
- Validate translations contain target language characters
- Retry failed/incomplete translations

---

## 10. Final Architecture

```
Input SRT
    ↓
Parse into blocks (index, timestamp, text)
    ↓
Format with [N] markers
    ↓
Check file size vs context_limit * 0.8
    ↓ (if too large)
Split into chunks (at sentence boundaries)
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

## 11. Commands Reference

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

| Feature | Status | Notes |
|---------|--------|-------|
| SRT format preservation | ✓ | Timestamps preserved |
| Context-aware translation | ✓ | Domain terminology support |
| Translation validation | ✓ | Retry on incomplete |
| context_limit for chunking | ✓ | Uses actual model capability |
| max_tokens configured | ✓ | Prevents output truncation |

**Core principle**: Understand the difference between input limits (context_limit) and output limits (max_tokens). Configure both correctly.
