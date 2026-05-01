"""
模型适配器基类
定义统一的接口，支持不同AI提供商
"""
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass


@dataclass
class ModelResponse:
    """统一的模型响应格式"""
    content: str
    provider: str
    model: str
    usage: dict[str, int]  # {prompt_tokens, completion_tokens, total_tokens}
    raw: dict[str, Any]


class ModelAdapter(ABC):
    """模型适配器抽象基类"""
    
    def __init__(self, api_key: str, api_base: str, model_id: str):
        self.api_key = api_key
        self.api_base = api_base
        self.model_id = model_id
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> ModelResponse:
        """
        统一的对话补全接口
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            ModelResponse: 统一的响应格式
        """
        pass
    
    def format_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        格式化消息（子类可以重写以适配不同格式）
        
        默认使用OpenAI格式：
        [{"role": "system|user|assistant", "content": "..."}]
        """
        return messages
    
    def extract_usage(self, raw_response: dict) -> dict[str, int]:
        """
        从原始响应中提取token使用量
        
        默认使用OpenAI格式：
        {"usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}}
        """
        usage = raw_response.get("usage", {})
        return {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
