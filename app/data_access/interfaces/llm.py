from abc import ABC, abstractmethod
from typing import List
from typing import AsyncIterator
from schemas.llm_schemas import ChatMessage


class LLMInterface(ABC):

    @abstractmethod
    async def generate(self, messages: List[ChatMessage]) -> str:
        """
        Generate a response based on the provided chat messages.

        Args:
            messages: A list of ChatMessage objects representing the conversation history.

        Returns:
            A string containing the generated response from the LLM.
        """
        pass

    @abstractmethod
    async def stream(self, messages: List[ChatMessage]) -> AsyncIterator[str]:
        """
        Stream a response based on the provided chat messages.

        Args:
            messages: A list of ChatMessage objects representing the conversation history.

        Yields:
            Chunks of the generated response from the LLM as they are produced.
        """
        pass
