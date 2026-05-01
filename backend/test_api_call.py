#!/usr/bin/env python3
"""测试实际 API 调用"""
import sys
import asyncio
sys.path.insert(0, ".")

from app.services.model_gateway import chat_completion

async def test_call():
    print("=" * 60)
    print("测试 API 调用...")
    print("=" * 60)
    
    try:
        result = await chat_completion(
            messages=[
                {"role": "system", "content": "你是一个有帮助的助手。"},
                {"role": "user", "content": "你好，请简单介绍一下你自己。"}
            ],
            temperature=0.7,
            max_tokens=100,
        )
        
        print("\n✓ API 调用成功!")
        print(f"\nProvider: {result.provider_id}")
        print(f"Model: {result.model_id}")
        print(f"\n回复内容:\n{result.content}")
        print(f"\n原始响应 (前200字符):\n{str(result.raw)[:200]}...")
        
    except Exception as e:
        print(f"\n✗ API 调用失败!")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
        import traceback
        print(f"\n完整堆栈:\n{traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(test_call())
