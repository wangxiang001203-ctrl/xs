#!/usr/bin/env python3
"""测试模型配置解析"""
import sys
sys.path.insert(0, ".")

from app.services.model_gateway import resolve_runtime
from app.services.workflow_config_service import get_active_model_config

print("=" * 60)
print("当前激活的模型配置:")
print("=" * 60)

active_config = get_active_model_config()
print(f"Provider: {active_config['provider']['name']}")
print(f"Provider ID: {active_config['provider']['id']}")
print(f"Provider API Base: {active_config['provider']['api_base']}")
print(f"Provider API Type: {active_config['provider']['api_type']}")
print()
print(f"Model: {active_config['model']['name']}")
print(f"Model ID: {active_config['model']['id']}")
print(f"Model API Type: {active_config['model'].get('api_type', 'NOT SET')}")
print(f"Model Tools: {active_config['model'].get('tools', 'NOT SET')}")

print("\n" + "=" * 60)
print("Runtime 解析结果:")
print("=" * 60)

runtime = resolve_runtime()
print(f"Provider ID: {runtime.provider_id}")
print(f"Provider Name: {runtime.provider_name}")
print(f"API Base: {runtime.api_base}")
print(f"API Type: {runtime.api_type}")
print(f"Model ID: {runtime.model_id}")
print(f"Model Name: {runtime.model_name}")
print(f"Tools: {runtime.tools}")
print(f"API Key (前10字符): {runtime.api_key[:10]}...")

print("\n" + "=" * 60)
print("预期的 API 端点:")
print("=" * 60)
if runtime.api_type in {"ark_responses", "responses"}:
    print(f"✓ 使用 Responses API: {runtime.api_base}/responses")
else:
    print(f"✗ 使用 Chat Completions API: {runtime.api_base}/chat/completions")
    print(f"  (但应该使用 /responses 端点)")
