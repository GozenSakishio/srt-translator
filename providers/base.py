from abc import ABC, abstractmethod
import httpx
from openai import OpenAI

class BaseProvider(ABC):
    def __init__(self, config: dict, api_key: str, timeout: float = 60.0):
        self.config = config
        self._max_tokens = config.get('max_tokens', 8000)
        if 'proxy' in config:
            trust_env = False
            proxy = config.get('proxy')
        else:
            trust_env = True
            proxy = None
        self.http_client = httpx.Client(
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            timeout=httpx.Timeout(timeout),
            proxy=proxy,
            trust_env=trust_env
        )
        self.client = OpenAI(
            api_key=api_key,
            base_url=config['base_url'],
            timeout=timeout,
            http_client=self.http_client
        )
        self.name = config['name']
        self.model = config['model']
    
    def close(self):
        if hasattr(self, 'http_client') and self.http_client:
            self.http_client.close()
            self.http_client = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
    
    def __del__(self):
        self.close()
    
    @abstractmethod
    def process(self, prompt: str, temperature: float = 0.7) -> str:
        pass

class OpenAICompatibleProvider(BaseProvider):
    def process(self, prompt: str, temperature: float = 0.7) -> str:
        extra_body = self.config.get('extra_params')
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=self._max_tokens,
            extra_body=extra_body
        )
        return response.choices[0].message.content
