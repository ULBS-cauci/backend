import asyncio
from typing import List

import torch
from FlagEmbedding import BGEM3FlagModel

from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.schemas.vector_schemas import SparseVectorSchema

# Use GPU (FP16) when CUDA is available, fall back to CPU (FP32) otherwise.
_CUDA_AVAILABLE: bool = torch.cuda.is_available()
_USE_FP16: bool = _CUDA_AVAILABLE
_BATCH_SIZE: int = 64 if _CUDA_AVAILABLE else 12


class BGEM3SparseEncoder(SparseEncoderInterface):
    def __init__(self, model_name: str = "BAAI/bge-m3") -> None:
        self._model = BGEM3FlagModel(model_name, use_fp16=_USE_FP16)

    async def encode_passages(self, texts: List[str]) -> List[SparseVectorSchema]:
        def _run() -> List[SparseVectorSchema]:
            output = self._model.encode(
                texts,
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False,
                batch_size=_BATCH_SIZE,
            )
            return [
                SparseVectorSchema(
                    indices=[int(k) for k in lex.keys()],
                    values=[float(v) for v in lex.values()],
                )
                for lex in output["lexical_weights"]
            ]

        return await asyncio.to_thread(_run)

    async def encode_query(self, text: str) -> SparseVectorSchema:
        def _run() -> SparseVectorSchema:
            output = self._model.encode(
                [text],
                return_dense=False,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            lex = output["lexical_weights"][0]
            return SparseVectorSchema(
                indices=[int(k) for k in lex.keys()],
                values=[float(v) for v in lex.values()],
            )

        return await asyncio.to_thread(_run)
