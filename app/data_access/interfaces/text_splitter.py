from abc import ABC, abstractmethod
from typing import List


class TextSplitterInterface(ABC):
    """Abstract Base Class for text splitting.

    Any custom implementation (e.g. using LangChain, custom logic, etc.)"""

    @abstractmethod
    def split_text(self, text: str) -> List[str]:
        """Splits the input text into smaller chunks based on the implemented logic."""
        pass