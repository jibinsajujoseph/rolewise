import os
import json
import asyncio
import hashlib
import time
from abc import ABC, abstractmethod
from typing import Type, Dict, Any, List, Optional
from pydantic import BaseModel

import openai
import anthropic
from google import genai
from google.genai import errors as genai_errors

# In-memory cache for list_models
_MODEL_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SECONDS = 600

def _get_cache_key(provider_id: str, api_key: str) -> str:
    return f"{provider_id}_{hashlib.sha256(api_key.encode()).hexdigest()}"

class ModelInfo(BaseModel):
    id: str
    display_name: str
    supports_structured_output: Optional[bool]

class LLMProvider(ABC):
    id: str
    name: str

    async def list_models(self, api_key: str) -> List[ModelInfo]:
        cache_key = _get_cache_key(self.id, api_key)
        cached = _MODEL_CACHE.get(cache_key)
        if cached and (time.time() - cached["timestamp"] < CACHE_TTL_SECONDS):
            return cached["models"]
        
        models = await self._fetch_models(api_key)
        _MODEL_CACHE[cache_key] = {"timestamp": time.time(), "models": models}
        return models

    @abstractmethod
    async def _fetch_models(self, api_key: str) -> List[ModelInfo]:
        pass

    @abstractmethod
    async def generate(
        self, api_key: str, model: str, system_prompt: str, user_prompt: str,
        response_schema: Type[BaseModel],
    ) -> Dict[str, Any]:
        pass

class GeminiProvider(LLMProvider):
    id = "gemini"
    name = "Google Gemini"

    async def _fetch_models(self, api_key: str) -> List[ModelInfo]:
        client = genai.Client(api_key=api_key)
        models = await asyncio.to_thread(client.models.list)
        result = []
        for m in models:
            if m.supported_actions and "generateContent" in m.supported_actions:
                result.append(ModelInfo(
                    id=m.name.replace("models/", "") if m.name else "unknown",
                    display_name=m.display_name or m.name or "unknown",
                    supports_structured_output=True
                ))
        return result

    async def generate(self, api_key: str, model: str, system_prompt: str, user_prompt: str, response_schema: Type[BaseModel]) -> Dict[str, Any]:
        client = genai.Client(api_key=api_key)
        retries = [1, 2, 4]
        for i in range(len(retries) + 1):
            try:
                response = await client.aio.models.generate_content(
                    model=model,
                    contents=user_prompt,
                    config={
                        "system_instruction": system_prompt,
                        "response_mime_type": "application/json",
                        "response_schema": response_schema,
                        "temperature": 0.1,
                    },
                )
                return json.loads(response.text)
            except genai_errors.ClientError as e:
                if e.code == 429 and i < len(retries):
                    await asyncio.sleep(retries[i])
                elif e.code == 429:
                    raise Exception("Gemini rate limit hit — wait a moment and try again.")
                else:
                    raise Exception(f"Failed to call Gemini: {str(e)}")
            except Exception as e:
                raise Exception(f"Failed to call Gemini: {str(e)}")

class OpenAIProvider(LLMProvider):
    id = "openai"
    name = "OpenAI"

    async def _fetch_models(self, api_key: str) -> List[ModelInfo]:
        client = openai.AsyncOpenAI(api_key=api_key)
        models = await client.models.list()
        result = []
        for m in models.data:
            if any(p in m.id.lower() for p in ["whisper", "tts", "dall-e", "embedding", "audio", "babbage", "davinci", "moderation"]):
                continue
            result.append(ModelInfo(
                id=m.id,
                display_name=m.id,
                supports_structured_output=True
            ))
        return sorted(result, key=lambda x: x.id)

    async def generate(self, api_key: str, model: str, system_prompt: str, user_prompt: str, response_schema: Type[BaseModel]) -> Dict[str, Any]:
        client = openai.AsyncOpenAI(api_key=api_key)
        retries = [1, 2, 4]
        for i in range(len(retries) + 1):
            try:
                completion = await client.beta.chat.completions.parse(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format=response_schema,
                    temperature=0.1
                )
                if completion.choices[0].message.parsed:
                    return completion.choices[0].message.parsed.model_dump()
                else:
                    raise Exception("Model refused or parsing failed.")
            except openai.RateLimitError:
                if i < len(retries):
                    await asyncio.sleep(retries[i])
                else:
                    raise Exception("OpenAI rate limit hit — wait a moment and try again.")
            except Exception as e:
                raise Exception(f"Failed to call OpenAI: {str(e)}")

class AnthropicProvider(LLMProvider):
    id = "anthropic"
    name = "Anthropic"

    async def _fetch_models(self, api_key: str) -> List[ModelInfo]:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        models = await client.models.list()
        result = []
        for m in models.data:
            supports_json = False
            try:
                cap = getattr(m, "capabilities", None)
                if isinstance(cap, dict):
                    struct_out = cap.get("structured_outputs", {})
                    supports_json = struct_out.get("supported", False)
                elif hasattr(m, 'model_dump'):
                    d = m.model_dump()
                    struct_out = d.get('capabilities', {}).get('structured_outputs', {})
                    supports_json = struct_out.get('supported', False)
            except Exception:
                pass
                
            result.append(ModelInfo(
                id=m.id,
                display_name=getattr(m, "display_name", m.id) or m.id,
                supports_structured_output=supports_json
            ))
        return result

    async def generate(self, api_key: str, model: str, system_prompt: str, user_prompt: str, response_schema: Type[BaseModel]) -> Dict[str, Any]:
        client = anthropic.AsyncAnthropic(api_key=api_key)
        retries = [1, 2, 4]
        for i in range(len(retries) + 1):
            try:
                response = await client.messages.parse(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                    output_format=response_schema,
                    temperature=0.1
                )
                if hasattr(response, "parsed"):
                    return response.parsed.model_dump()
                raise Exception("Refusal or incomplete parse.")
            except anthropic.RateLimitError:
                if i < len(retries):
                    await asyncio.sleep(retries[i])
                else:
                    raise Exception("Anthropic rate limit hit — wait a moment and try again.")
            except Exception as e:
                raise Exception(f"Failed to call Anthropic: {str(e)}")

class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, base_url: str, name: str, id_: str):
        self.base_url = base_url
        self.name = name
        self.id = id_

    async def _fetch_models(self, api_key: str) -> List[ModelInfo]:
        client = openai.AsyncOpenAI(api_key=api_key, base_url=self.base_url)
        models = await client.models.list()
        result = []
        for m in models.data:
            if "whisper" in m.id.lower():
                continue
            result.append(ModelInfo(
                id=m.id,
                display_name=m.id,
                supports_structured_output=None
            ))
        return sorted(result, key=lambda x: x.id)

    async def generate(self, api_key: str, model: str, system_prompt: str, user_prompt: str, response_schema: Type[BaseModel]) -> Dict[str, Any]:
        client = openai.AsyncOpenAI(api_key=api_key, base_url=self.base_url)
        retries = [1, 2, 4]
        
        # Try strict parsing first
        for i in range(len(retries) + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={
                        "type": "json_schema", 
                        "json_schema": {
                            "name": response_schema.__name__, 
                            "schema": response_schema.model_json_schema(), 
                            "strict": True
                        }
                    },
                    temperature=0.1
                )
                content = response.choices[0].message.content
                return response_schema.model_validate_json(content).model_dump()
            except openai.RateLimitError:
                if i < len(retries):
                    await asyncio.sleep(retries[i])
                else:
                    raise Exception(f"{self.name} rate limit hit — wait a moment and try again.")
            except Exception as e:
                if "rate limit hit" not in str(e).lower():
                    break
                elif i == len(retries):
                    raise Exception(f"{self.name} rate limit hit — wait a moment and try again.")

        # Fallback to json_object format with prompt instructions
        schema_str = json.dumps(response_schema.model_json_schema(), indent=2)
        fallback_prompt = user_prompt + f"\n\nIMPORTANT: You must return a JSON object that strictly adheres to the following JSON schema:\n{schema_str}"
        for i in range(len(retries) + 1):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": fallback_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                content = response.choices[0].message.content
                return response_schema.model_validate_json(content).model_dump()
            except openai.RateLimitError:
                if i < len(retries):
                    await asyncio.sleep(retries[i])
                else:
                    raise Exception(f"{self.name} rate limit hit — wait a moment and try again.")
            except Exception as e:
                if i == len(retries):
                    raise Exception(f"Failed to call {self.name} (fallback): {str(e)}")


PROVIDERS: Dict[str, LLMProvider] = {
    "gemini": GeminiProvider(),
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "groq": OpenAICompatibleProvider(base_url="https://api.groq.com/openai/v1", name="Groq", id_="groq"),
    "openrouter": OpenAICompatibleProvider(base_url="https://openrouter.ai/api/v1", name="OpenRouter", id_="openrouter"),
}
