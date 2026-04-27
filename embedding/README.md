# Mini tutorial — Embedding + retrieval semantic cu Qwen3

Script-ul `test_embedding.py` e un mini-tutorial
care iti arata pas cu pas cum functioneaza modelul de embedding QWEN3 cu 4B de parametrii si cum faci
retrieval semantic peste un text.

---

## Instalare

> ### pip install -r requirments.txt

## Rulare

```
1. Activeaza .venv
2. python test_embedding.py
```

**Prima rulare dureaza ~2-3 minute** — se descarca modelul `Qwen/Qwen3-Embedding-4B`
(~8 GB) in cache-ul HuggingFace:

- macOS / Linux: `~/.cache/huggingface/hub/`
- Windows: `C:\Users\<tu>\.cache\huggingface\hub\`

---

## Ce ar trebui sa vezi

Vectorul de embedding pentru fiecare propoziție (2560 de valori) și similaritatea semantică dintre ele — mare pentru propoziții cu sens similar, mică pentru
propoziții diferite.

---
