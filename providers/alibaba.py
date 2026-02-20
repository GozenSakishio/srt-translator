import os
from .base import OpenAICompatibleProvider

class AlibabaProvider(OpenAICompatibleProvider):
    def __init__(self, config: dict, timeout: float = 60.0):
        api_key = os.getenv('ALIBABA_API_KEY')
        if not api_key:
            raise ValueError("ALIBABA_API_KEY not found in environment")
        super().__init__(config, api_key, timeout)
