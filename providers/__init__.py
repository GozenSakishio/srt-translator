from .base import BaseProvider
from .siliconflow import SiliconFlowProvider
from .alibaba import AlibabaProvider
from .openrouter import OpenRouterProvider

def create_provider(provider_config: dict, timeout: float = 60.0) -> BaseProvider:
    name = provider_config['name']
    
    if name == 'siliconflow':
        return SiliconFlowProvider(provider_config, timeout)
    elif name == 'alibaba':
        return AlibabaProvider(provider_config, timeout)
    elif name == 'openrouter':
        return OpenRouterProvider(provider_config, timeout)
    else:
        raise ValueError(f"Unknown provider: {name}")

def get_enabled_providers(config: dict) -> list:
    providers = []
    rate_config = config.get('rate_limit', {})
    timeout = rate_config.get('timeout', 60.0)
    for p in config['providers']:
        if p.get('enabled', True):
            try:
                providers.append(create_provider(p, timeout))
            except ValueError as e:
                print(f"Warning: {e}")
    return providers
