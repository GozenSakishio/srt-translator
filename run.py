#!/usr/bin/env python3
import re
import time
import argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv

from providers import get_enabled_providers

load_dotenv()

INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
CONFIG_FILE = Path("config.yaml")

SAFETY_MARGIN = 0.75
OUTPUT_RESERVE = 0.5
CHARS_PER_TOKEN = 1.5


def get_effective_chunk_size(providers) -> int:
    min_context = min(p._context_window for p in providers)
    return int(min_context * SAFETY_MARGIN * OUTPUT_RESERVE)


def get_max_tokens_for_chunk(providers, chunk_chars: int) -> int:
    min_context = min(p._context_window for p in providers)
    input_tokens = int(chunk_chars / CHARS_PER_TOKEN)
    return min_context - input_tokens


def load_config():
    with open(CONFIG_FILE, encoding='utf-8') as f:
        return yaml.safe_load(f)


def read_srt(file_path: Path) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def parse_srt(srt_content: str) -> list[dict]:
    blocks = []
    current_block = {}
    lines = srt_content.strip().split('\n')
    
    for line in lines:
        line = line.rstrip()
        if not line:
            if current_block:
                blocks.append(current_block)
                current_block = {}
            continue
        
        if 'index' not in current_block and line.isdigit():
            current_block['index'] = int(line)
        elif 'timestamp' not in current_block and re.match(r'\d{2}:\d{2}:\d{2}', line):
            current_block['timestamp'] = line
        else:
            if 'text' not in current_block:
                current_block['text'] = []
            current_block['text'].append(line)
    
    if current_block:
        blocks.append(current_block)
    
    return blocks


def blocks_to_translatable_text(blocks: list[dict]) -> str:
    lines = []
    for block in blocks:
        text = ' '.join(block['text'])
        lines.append(f"[{block['index']}] {text}")
    return '\n'.join(lines)


def parse_translated_text(text: str, expected_count: int) -> list[str]:
    pattern = r'\[(\d+)\]\s*(.*?)(?=\[\d+\]|$)'
    matches = re.findall(pattern, text, re.DOTALL)
    
    results = {}
    for idx_str, content in matches:
        idx = int(idx_str)
        content = content.strip()
        if content:
            results[idx] = content
    
    output = []
    for i in range(1, expected_count + 1):
        output.append(results.get(i, ''))
    
    return output


def build_srt(blocks: list[dict], translated_texts: list[str]) -> str:
    output = []
    for i, block in enumerate(blocks):
        output.append(str(i + 1))
        output.append(block['timestamp'])
        if i < len(translated_texts) and translated_texts[i]:
            output.append(translated_texts[i])
        else:
            output.extend(block['text'])
        output.append('')
    return '\n'.join(output)


def split_text_into_chunks(text: str, max_size: int) -> list[str]:
    sentences = re.split(r'(?<=[。.!?])\s*', text)
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sent_size = len(sentence)
        if current_size + sent_size + 1 > max_size and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(sentence)
        current_size += sent_size + 1
    
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def process_with_fallback(providers, prompt: str, config: dict, max_tokens: int | None = None) -> tuple[str, str]:
    rate_config = config['rate_limit']
    max_retries = rate_config.get('max_retries', 3)
    retry_delay = rate_config.get('retry_delay', 5)
    
    for provider in providers:
        for attempt in range(max_retries):
            try:
                print(f"    Trying {provider.name} ({provider.model}) attempt {attempt + 1}/{max_retries}")
                result = provider.process(prompt, max_tokens=max_tokens)
                return result, provider.name
            except Exception as e:
                import traceback
                print(f"    Error with {provider.name}: {e}")
                if attempt == 0:
                    print(f"    Debug traceback: {traceback.format_exc().splitlines()[-3:]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
    
    raise RuntimeError("All providers failed")


def validate_translation(original: str, translated: str, target_lang: str = "Chinese") -> bool:
    if target_lang.lower() in ("chinese", "zh", "中文"):
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', translated))
        ratio = chinese_chars / len(translated) if translated else 0
        return ratio >= 0.3
    return True


def process_large_text(providers, raw_text: str, config: dict) -> tuple[str, str | None]:
    chunk_size = get_effective_chunk_size(providers)
    if len(raw_text) <= chunk_size:
        prompt_template = config['processing']['prompt']
        source_lang = config['processing'].get('source_language', 'auto')
        target_lang = config['processing'].get('target_language', 'Chinese')
        prompt = prompt_template.format(
            source_language=source_lang,
            target_language=target_lang,
            content=raw_text
        )
        max_tokens = get_max_tokens_for_chunk(providers, len(raw_text))
        return process_with_fallback(providers, prompt, config, max_tokens)
    
    chunks = split_text_into_chunks(raw_text, chunk_size)
    print(f"    Split into {len(chunks)} chunks ({[len(c) for c in chunks]} chars each)")
    
    prompt_template = config['processing']['prompt']
    source_lang = config['processing'].get('source_language', 'auto')
    target_lang = config['processing'].get('target_language', 'Chinese')
    results = []
    last_provider = None
    
    for i, chunk in enumerate(chunks):
        print(f"    Processing chunk {i+1}/{len(chunks)}...")
        prompt = prompt_template.format(
            source_language=source_lang,
            target_language=target_lang,
            content=chunk
        )
        max_tokens = get_max_tokens_for_chunk(providers, len(chunk))
        result, provider = process_with_fallback(providers, prompt, config, max_tokens)
        results.append(result)
        last_provider = provider
        if i < len(chunks) - 1:
            delay = 60.0 / config['rate_limit']['requests_per_minute']
            time.sleep(delay)
    
    combined = '\n\n'.join(results)
    return combined, last_provider


def main():
    parser = argparse.ArgumentParser(description='Translate SRT subtitle files with AI')
    parser.add_argument('--provider', '-p', 
                        help='Use only this provider (e.g., alibaba, openrouter, siliconflow)')
    parser.add_argument('--list-providers', '-l', 
                        action='store_true',
                        help='List available providers and exit')
    parser.add_argument('--source', '-s',
                        help='Source language (overrides config)')
    parser.add_argument('--target', '-t',
                        help='Target language (overrides config)')
    args = parser.parse_args()
    
    config = load_config()
    
    if args.list_providers:
        print("Available providers in config:")
        for p in config['providers']:
            status = "enabled" if p.get('enabled', True) else "disabled"
            print(f"  - {p['name']} ({p['model']}) [{status}]")
        return
    
    if args.source:
        config['processing']['source_language'] = args.source
    if args.target:
        config['processing']['target_language'] = args.target
    
    providers = get_enabled_providers(config)
    
    if args.provider:
        providers = [p for p in providers if p.name == args.provider]
        if not providers:
            print(f"Error: Provider '{args.provider}' not found or not enabled")
            print(f"Available: {[p.name for p in get_enabled_providers(config)]}")
            return
        print(f"Using only: {args.provider}")
    
    if not providers:
        print("Error: No available providers. Check your API keys.")
        return
    
    print(f"Available providers: {[p.name for p in providers]}")
    print(f"Source: {config['processing'].get('source_language', 'auto')} -> Target: {config['processing'].get('target_language', 'Chinese')}")
    
    srt_files = list(INPUT_DIR.glob("*.srt"))
    
    if not srt_files:
        print("No .srt files found in input/")
        return
    
    print(f"\nProcessing {len(srt_files)} SRT file(s)...\n")
    
    rate_config = config['rate_limit']
    delay = 60.0 / rate_config['requests_per_minute']
    
    try:
        for i, srt_file in enumerate(srt_files, 1):
            print(f"[{i}/{len(srt_files)}] {srt_file.name}")
            
            try:
                srt_content = read_srt(srt_file)
                blocks = parse_srt(srt_content)
                
                if not blocks:
                    print(f"    Skipping: No subtitle blocks found")
                    continue
                
                raw_text = blocks_to_translatable_text(blocks)
                
                if not raw_text.strip():
                    print(f"    Skipping: No text content found")
                    continue
                
                translated_text, used_provider = process_large_text(providers, raw_text, config)
                
                translated_texts = parse_translated_text(translated_text, len(blocks))
                
                target_lang = config['processing'].get('target_language', 'Chinese')
                untranslated = []
                for idx, (orig_text, trans_text) in enumerate(zip(blocks, translated_texts)):
                    combined = ' '.join(orig_text['text'])
                    if trans_text and not validate_translation(combined, trans_text, target_lang):
                        untranslated.append(idx + 1)
                
                if untranslated:
                    print(f"    WARNING: {len(untranslated)} blocks may be untranslated: {untranslated[:10]}{'...' if len(untranslated) > 10 else ''}")
                
                output_content = build_srt(blocks, translated_texts)
                
                output_file = OUTPUT_DIR / f"{srt_file.stem}.srt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(output_content)
                
                print(f"    Done via {used_provider} -> {output_file.name}")
                
            except Exception as e:
                print(f"    Failed: {e}")
            
            if i < len(srt_files):
                time.sleep(delay)
    finally:
        for provider in providers:
            try:
                provider.close()
            except Exception:
                pass
    
    print("\nAll done!")


if __name__ == "__main__":
    main()
