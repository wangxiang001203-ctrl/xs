"""
模型适配器模块
支持不同AI提供商的API适配
"""
from .base import ModelAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .google_adapter import GoogleAdapter
from .ernie_adapter import ErnieAdapter

__all__ = [
    "ModelAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "ErnieAdapter",
]
