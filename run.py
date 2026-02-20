#!/usr/bin/env python3
import os
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
MAX_CHUNK_SIZE = 12000
SUPPORTED_EXTENSIONS = {'.txt', '.md', '.text'}


def load_config():
    with open(CONFIG_FILE, encoding='utf-8') as f:
        return yaml.safe_load(f)


def read_file(file_path: Path) -> str:
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def split_text_into_chunks(text: str, max_size: int = MAX_CHUNK_SIZE) -> list[str]:
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        para_size = len(para)
        if current_size + para_size + 2 > max_size and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            current_chunk = []
            current_size = 0
        current_chunk.append(para)
        current_size += para_size + 2
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def process_with_fallback(providers, prompt: str, config: dict) -> tuple[str, str]:
    rate_config = config['rate_limit']
    max_retries = rate_config.get('max_retries', 3)
    retry_delay = rate_config.get('retry_delay', 5)
    
    for provider in providers:
        for attempt in range(max_retries):
            try:
                print(f"    Trying {provider.name} ({provider.model}) attempt {attempt + 1}/{max_retries}")
                result = provider.process(prompt)
                return result, provider.name
            except Exception as e:
                import traceback
                print(f"    Error with {provider.name}: {e}")
                if attempt == 0:
                    print(f"    Debug traceback: {traceback.format_exc().splitlines()[-3:]}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
    
    raise RuntimeError("All providers failed")


def process_large_text(providers, raw_text: str, config: dict) -> tuple[str, str]:
    if len(raw_text) <= MAX_CHUNK_SIZE:
        prompt_template = config['processing']['prompt']
        source_lang = config['processing'].get('source_language', 'auto')
        target_lang = config['processing'].get('target_language', 'Chinese')
        prompt = prompt_template.format(
            source_language=source_lang,
            target_language=target_lang,
            content=raw_text
        )
        return process_with_fallback(providers, prompt, config)
    
    chunks = split_text_into_chunks(raw_text)
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
        result, provider = process_with_fallback(providers, prompt, config)
        results.append(result)
        last_provider = provider
        if i < len(chunks) - 1:
            delay = 60.0 / config['rate_limit']['requests_per_minute']
            time.sleep(delay)
    
    combined = '\n\n'.join(results)
    return combined, last_provider


def main():
    parser = argparse.ArgumentParser(description='Translate text files with AI')
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
    print(f"Source: {config['processing'].get('source_language', 'auto')} → Target: {config['processing'].get('target_language', 'Chinese')}")
    
    input_files = []
    for ext in SUPPORTED_EXTENSIONS:
        input_files.extend(INPUT_DIR.glob(f"*{ext}"))
    
    if not input_files:
        print(f"No files found in input/ (supported: {SUPPORTED_EXTENSIONS})")
        return
    
    print(f"\nProcessing {len(input_files)} file(s)...\n")
    
    rate_config = config['rate_limit']
    delay = 60.0 / rate_config['requests_per_minute']
    include_title = config['processing'].get('include_filename_as_title', True)
    
    try:
        for i, input_file in enumerate(input_files, 1):
            print(f"[{i}/{len(input_files)}] {input_file.name}")
            
            try:
                raw_text = read_file(input_file)
                
                if not raw_text.strip():
                    print(f"    Skipping: No text content found")
                    continue
                
                translated_text, used_provider = process_large_text(providers, raw_text, config)
                
                output_lines = []
                if include_title:
                    title = input_file.stem
                    output_lines.append(f"# {title}\n")
                output_lines.append(translated_text)
                
                output_file = OUTPUT_DIR / f"{input_file.stem}.txt"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(output_lines))
                
                print(f"    Done via {used_provider} -> {output_file.name}")
                
            except Exception as e:
                print(f"    Failed: {e}")
            
            if i < len(input_files):
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
