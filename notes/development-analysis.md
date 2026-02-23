# Development Analysis - Objective Review

## Problem Statement
master branch produces incomplete translations (some blocks untranslated), while version-0.0.1 produces complete translations.

---

## Solution (v0.0.2)

### Single Source of Truth
Use `context_window` from model documentation (e.g., qwen3-8b = 32k tokens).

### Chunk Size Formula
```python
SAFETY_MARGIN = 0.75    # 25% for prompt overhead
OUTPUT_RESERVE = 0.5    # 50% for output
CHARS_PER_TOKEN = 1.5   # Conservative estimate for Chinese

input_limit = context_window * SAFETY_MARGIN * OUTPUT_RESERVE * CHARS_PER_TOKEN
```

For 32k context: 32000 × 0.75 × 0.5 × 1.5 = 18000 chars

### API Call
Remove `max_tokens` parameter - let provider use its default output limit.

### Translation Validation
Detect untranslated blocks by checking Chinese character ratio (< 30% indicates untranslated).

---

## Technical Analysis

### 1. Token Calculation Issue

**From OpenAI's tiktoken documentation:**
- Chinese text uses ~1.5-2 tokens per character (varies by tokenizer)
- For Qwen models: approximately 1.5-2 chars per token for Chinese
- Each message has overhead: ~3-4 tokens for formatting

**version-0.0.1 approach:**
```
MAX_CHUNK_SIZE = 12000  # Fixed value
```
- Input: 12000 chars → Output: ~12000 Chinese chars → ~6000-8000 tokens
- Stays within max_tokens=8000 limit with margin

**master approach:**
```python
output_limit_chars = int(min_output * 1.8)  # 8000 * 1.8 = 14400
```
- Input: 14400 chars → Output: ~14400 Chinese chars → ~7200-9600 tokens
- **May exceed max_tokens=8000 when translation output is dense**

**Objective issue:** The 1.8 multiplier assumes optimal token efficiency, but Chinese text can be less efficient.

### 2. Prompt Overhead Not Accounted

**From OpenAI/Anthropic documentation:**
- System prompt + user message formatting adds ~10-50 tokens overhead
- Complex prompts with examples add more

**version-0.0.1 prompt:** ~50 words → ~70 tokens overhead
**master prompt:** ~100 words + context/style → ~150+ tokens overhead

The effective output capacity is: `max_tokens - prompt_overhead`

### 3. Context Limit vs Output Limit Confusion

**From documentation:**
| Parameter | Controls | Typical Value |
|-----------|----------|---------------|
| context_limit | INPUT size | 32k+ tokens |
| max_tokens | OUTPUT size | 4k-16k tokens |

**Critical mistake:** The master code calculates chunk size based on output limit (max_tokens), but the safety margin (0.8) is applied to context_limit:

```python
return min(int(min_context * SAFETY_MARGIN), output_limit_chars)
#                        ^^^^^^^^^^^^ applied to wrong limit
```

The correct approach: chunk size should be based on **output capacity**, not input context window.

---

## Best Practices (From Official Documentation)

### Token Counting (OpenAI tiktoken docs)

> "Knowing how many tokens are in a text string can tell you (a) whether the string is too long for a text model to process and (b) how much an API call costs"

**Recommendation:** Use tiktoken to count tokens accurately instead of character-based estimation.

### Long Context Tips (Anthropic docs)

1. **Put long data at the top** - improves model attention
2. **Structure with clear markers** - use consistent format like [N] for indices
3. **Quote relevant parts first** - helps model focus on correct content

### Output Truncation Prevention

Best practices for avoiding output truncation:

1. **Reserve margin:** `effective_max = max_tokens * 0.7` (30% safety margin)
2. **Account for prompt overhead:** `output_budget = effective_max - prompt_tokens`
3. **Test empirically:** Run real-world tests with your specific content

---

## Root Cause Summary

| Issue | v0.0.1 | master | Assessment |
|-------|--------|--------|------------|
| Chunk size | 12000 chars fixed | ~14400 chars dynamic | master is too aggressive |
| Safety margin | Implicit (~25%) | 20% on wrong limit | master applies margin incorrectly |
| Prompt overhead | Small (~70 tokens) | Larger (~150 tokens) | master uses more of output budget |
| Token estimation | N/A | 1.8 chars/token | Inaccurate for Chinese |

**Key insight:** version-0.0.1's fixed 12000 chars happens to be `8000 * 1.5 = 12000`, which is a conservative estimate with built-in safety margin. The master's "optimized" calculation removed this safety margin.

---

## Recommended Values (Based on Docs)

### For Alibaba qwen3-8b (max_tokens=8000):

```
Safe output budget = 8000 * 0.7 = 5600 tokens
Prompt overhead ≈ 200 tokens
Available for translation = 5400 tokens
Chinese chars ≈ 5400 * 1.5 = 8100 chars (input ≈ output)

With safety margin: 8000 chars input max
```

### For SiliconFlow/OpenRouter (max_tokens=16000):

```
Safe output budget = 16000 * 0.7 = 11200 tokens
Prompt overhead ≈ 200 tokens
Available for translation = 11000 tokens
Chinese chars ≈ 11000 * 1.5 = 16500 chars

With safety margin: 14000 chars input max
```

### Recommended Formula:

```python
def get_safe_chunk_size(max_tokens: int, prompt_tokens: int = 200) -> int:
    SAFE_MARGIN = 0.7  # Reserve 30% for safety
    CHARS_PER_TOKEN = 1.5  # Conservative for Chinese
    return int((max_tokens * SAFE_MARGIN - prompt_tokens) * CHARS_PER_TOKEN)
```

---

## Previous Issues (Resolved)

| Issue | v0.0.1 | master | v0.0.2 (Current) |
|-------|--------|--------|------------------|
| Chunk size | 12000 chars fixed | ~14400 chars dynamic | Dynamic from context_window |
| Safety margin | Implicit (~25%) | Applied incorrectly | Explicit 0.75 factor |
| Token estimation | N/A | 1.8 chars/token | 1.5 chars/token (conservative) |
| Validation | None | None | Chinese char ratio check |
| Config param | max_tokens (confusing) | max_tokens + context_limit | context_window only |

---

## Lessons for Future Development

### 1. Decouple Variables
When multiple parameters interact (chunk size, prompt length, token limits), change ONE at a time and validate.

### 2. Use Actual Token Counting
Don't estimate with character counts. Use tiktoken or equivalent:
```python
import tiktoken
encoding = tiktoken.encoding_for_model("gpt-4")  # or appropriate
token_count = len(encoding.encode(text))
```

### 3. Empirical Testing
Before optimizing parameters:
1. Run baseline test
2. Measure actual token usage (from API response)
3. Calculate real ratios for your content type

### 4. Documentation First
Check official docs for:
- Token counting methods
- Context window vs output limits
- Best practices for the specific task

---

## Next Steps

1. **Keep chunk_size simple:** Use fixed conservative values or formula with 0.7 safety margin
2. **Add token counting:** Use tiktoken to verify input/output sizes
3. **Monitor API responses:** Log `usage.total_tokens` to understand real consumption
4. **Simplify prompt:** Shorter prompt = more output budget
