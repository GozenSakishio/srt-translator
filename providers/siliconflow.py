import os
from .base import OpenAICompatibleProvider

class SiliconFlowProvider(OpenAICompatibleProvider):
    def __init__(self, config: dict, timeout: float = 60.0):
        api_key = os.getenv('SILICONFLOW_API_KEY')
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY not found in environment")
        super().__init__(config, api_key, timeout)
