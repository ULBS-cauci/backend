import numpy as np
import torch
from sentence_transformers import SentenceTransformer

device = "mps" if torch.backends.mps.is_available() else "cpu"

model = SentenceTransformer(
    "Qwen/Qwen3-Embedding-4B",
    device=device,
    model_kwargs={"torch_dtype": torch.bfloat16},
)

texts = [
    "Cainele alearga in parc.",
    "Un catelus se joaca afara.",      
    "Compilatorul C compileaza codul.", 
]

embeddings = model.encode(texts, normalize_embeddings=True)

print(f"Dimensiune vector: {embeddings.shape[1]}\n")
for text,emb in zip(texts,embeddings):
    print(f"Text : {text}")
    print(f"Primele valori din embedding: {emb[:10]}\n")

def similarity(a, b):
    return float(np.dot(a, b))

print("Similaritate semantica (cosine):")
print(f"  'Caine in parc'  vs  'Catelus afara'     → {similarity(embeddings[0], embeddings[1]):.4f}  (ar trebui mare)")
print(f"  'Caine in parc'  vs  'Compilator C'       → {similarity(embeddings[0], embeddings[2]):.4f}  (ar trebui mic)")
print(f"  'Catelus afara'  vs  'Compilator C'       → {similarity(embeddings[1], embeddings[2]):.4f}  (ar trebui mic)")
