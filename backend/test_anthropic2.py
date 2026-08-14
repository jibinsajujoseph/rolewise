import anthropic
import inspect

client = anthropic.AsyncAnthropic(api_key="sk-test")
print("Parse args:", inspect.signature(client.messages.parse))
