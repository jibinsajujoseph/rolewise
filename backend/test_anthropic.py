import anthropic
import asyncio

async def test():
    client = anthropic.AsyncAnthropic(api_key="sk-test")
    print("Has parse:", hasattr(client.messages, "parse"))
    print("Create args:", dir(client.messages.create))
    
asyncio.run(test())
