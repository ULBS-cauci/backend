import asyncio
import uuid
from typing import AsyncIterator, List, Optional
from sqlmodel import select, desc, asc
from sqlmodel.ext.asyncio.session import AsyncSession
import datetime
import logging

logger = logging.getLogger("uvicorn.error")

from app.rag_engine.fusion import rrf_fuse
from app.rag_engine.query_rewrite import build_condensation_messages
from app.data_access.interfaces.llm import LLMInterface
from app.schemas.chat_schemas import Conversation, Message, MessageSender
from app.schemas.llm_schemas import ChatMessage, MessageRole
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.interfaces.reranker import RerankerInterface

from fastapi import HTTPException, status

TUTOR_SYSTEM_PROMPT = (
    "You are a university tutor for the AI Tutor platform. "
    "Help students understand concepts clearly and concisely. "
    "If you are not sure about something, say so."
)


class ChatService:
    def __init__(
        self,
        vector_db: VectorDBInterface,
        embedding_client: EmbeddingInterface,
        llm_client: LLMInterface,
        sparse_encoder: SparseEncoderInterface,
        reranker: RerankerInterface,
        score_threshold: float,
        db_session: AsyncSession,
    ):
        self.vector_db = vector_db
        self.embedding_client = embedding_client
        self.llm_client = llm_client
        self.sparse_encoder = sparse_encoder
        self.reranker = reranker
        self.score_threshold = score_threshold
        self.db_session = db_session

    async def create_conversation(self, user_id: uuid.UUID) -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title="New Conversation_" + datetime.datetime.now().isoformat(),
        )
        self.db_session.add(conversation)
        await self.db_session.flush()
        await self.db_session.refresh(conversation)
        return conversation

    async def get_user_conversations(self, user_id: uuid.UUID) -> List[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
        )
        result = await self.db_session.exec(stmt)
        return list(result.all())

    async def get_conversation_for_user(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> Optional[Conversation]:
        conversation = await self.db_session.get(Conversation, conversation_id)
        if conversation and conversation.user_id == user_id:
            return conversation
        return None

    async def get_conversation_messages(
        self, conversation_id: uuid.UUID
    ) -> List[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(asc(Message.created_at))
        )
        result = await self.db_session.exec(stmt)
        return list(result.all())

    async def ask_stream(
        self,
        query: str,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> AsyncIterator[str]:
        conversation_id = await self._get_or_create_conversation(
            user_id, conversation_id, query
        )
        messages = await self._prepare_llm_messages(conversation_id, query)
        await self._persist_message(conversation_id, MessageSender.USER, query)

        chunks = []
        async for chunk in self.llm_client.stream(messages):
            chunks.append(chunk)
            yield chunk

        await self._persist_message(conversation_id, MessageSender.AI, "".join(chunks))

    async def _get_or_create_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: Optional[uuid.UUID],
        query: str,
    ) -> uuid.UUID:
        if not conversation_id:
            title = query[:50] + "..." if len(query) > 50 else query
            conversation = Conversation(user_id=user_id, title=title)
            self.db_session.add(conversation)
            await self.db_session.flush()
            await self.db_session.refresh(conversation)
            return conversation.id

        conversation = await self.get_conversation_for_user(conversation_id, user_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or unauthorized",
            )
        conversation.updated_at = datetime.datetime.now(datetime.timezone.utc).replace(
            tzinfo=None
        )
        self.db_session.add(conversation)
        await self.db_session.flush()
        return conversation_id

    async def _condense_query(self, history: List[Message], query: str) -> str:
        if not history:
            return query
        condensation_messages = build_condensation_messages(history, query)
        condensed = await self.llm_client.generate(condensation_messages)
        logger.info(f"Condensed query: '{query}' → '{condensed}'")
        return condensed

    async def _prepare_llm_messages(
        self, conversation_id: uuid.UUID, query: str
    ) -> List[ChatMessage]:
        history = await self.get_conversation_messages(conversation_id)
        search_query = await self._condense_query(history, query)

        messages: List[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=TUTOR_SYSTEM_PROMPT)
        ]
        for msg in history:
            role = (
                MessageRole.USER
                if msg.sender == MessageSender.USER
                else MessageRole.ASSISTANT
            )
            messages.append(ChatMessage(role=role, content=msg.content))

        context = await self._retrieve_relevant_chunks(
            search_query, collection_name="university_library"
        )  # TODO: collection_name should come from session/material metadata
        if context:
            logger.info(f"Retrieved context for query '{query}': {context}")
            messages.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content="Here are some relevant documents from the university library that might help you answer the question:",
                )
            )
            messages.append(ChatMessage(role=MessageRole.SYSTEM, content=context))
        else:
            messages.append(
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content=(
                        "No relevant content was found in the knowledge base for this query. "
                        "Politely tell the student that the topic is outside the scope of the uploaded "
                        "course materials and that you cannot answer it. Do not answer from general knowledge."
                    ),
                )
            )

        messages.append(ChatMessage(role=MessageRole.USER, content=query))
        return messages

    async def _persist_message(
        self, conversation_id: uuid.UUID, sender: MessageSender, content: str
    ) -> None:
        self.db_session.add(
            Message(conversation_id=conversation_id, sender=sender, content=content)
        )
        await self.db_session.commit()

    async def _retrieve_relevant_chunks(
        self,
        query: str,
        collection_name: str,
        limit: int = 5,
    ) -> str:
        """
        Embed the query with both dense and sparse encoders, run hybrid search (RRF),
        and return the retrieved chunks joined as a single string.

        Args:
            query: The student's question to embed and search against.
            collection_name: The Qdrant collection to search (maps to a specific material).
            limit: Maximum number of chunks to return after RRF fusion.

        Returns:
            A single string of relevant chunk texts separated by '---', or an empty string
            if no chunks are found.
        """
        query_vector, sparse_query = await asyncio.gather(
            self.embedding_client.embed_text(query),
            self.sparse_encoder.encode_query(query),
        )

        semantic_results, keyword_results = await asyncio.gather(
            self.vector_db.search(collection_name, query_vector, limit=limit * 4),
            self.vector_db.search_sparse(
                collection_name, sparse_query, limit=limit * 4
            ),
            return_exceptions=True,
        )

        if isinstance(semantic_results, Exception):
            raise semantic_results
        if isinstance(keyword_results, Exception):
            logger.warning(
                f"Sparse search failed for '{collection_name}' — falling back to dense-only. "
                f"Reindex with sparse=True to restore hybrid retrieval. Error: {keyword_results}"
            )
            keyword_results = []

        fused = rrf_fuse(semantic_results, keyword_results, limit=limit * 2)
        reranked = await self.reranker.rerank(query, fused, top_n=limit)
        above_threshold = [res for res in reranked if res.score >= self.score_threshold]
        if not above_threshold:
            logger.info(
                f"No chunks above threshold {self.score_threshold} for query '{query}'"
            )
            return ""
        return "\n---\n".join(res.chunk.text for res in above_threshold)
