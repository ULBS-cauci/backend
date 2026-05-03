from openai import AsyncOpenAI
from typing import List, AsyncIterator

from app.data_access.interfaces.llm import LLMInterface
from app.schemas.llm_schemas import ChatMessage




class OpenAILLMCClient(LLMInterface):
    def __init__(self,api_key:str,model:str,temperature:float):
        self._client = AsyncOpenAI(api_key=api_key)
        self._model=model
        self._temperature=temperature


    async def generate(self,messages: List[ChatMessage]) -> str:
        response =  await self._client.chat.completions.create(
            model = self._model,
            temperature = self._temperature,
            messages= self._to_openai(messages),
        )
        return response.choices[0].message.content or ""
    

    async def stream(self, messages: List[ChatMessage])->AsyncIterator[str]:
        response_stream = await self._client.chat.completions.create(
            model= self._model,
            temperature = self._temperature,
            messages = self._to_openai(messages),
            stream=True,
        )
        async for chunk in response_stream:
            content = chunk.choices[0].delta.content 
            if content:
                yield content
                
    @staticmethod
    def _to_openai(messages: List[ChatMessage]) -> List[dict]:
        """Convert our domain ChatMessage to the dict format OpenAI expects."""
        return [{"role": m.role.value, "content": m.content} for m in messages]

