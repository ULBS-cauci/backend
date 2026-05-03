# Local Embedding Model Setup

## Why Ollama?
As we build our RAG application, our team is working across a mix of hardware—one Mac with Apple Silicon, two laptops with NVIDIA GPUs, and one CPU-only laptop. To avoid the nightmare of cross-platform Docker GPU configurations on local machines, we are standardizing on **native Ollama for local development**.

This ensures that everyone gets maximum hardware acceleration (using Metal, CUDA, or CPU) right out of the box without fighting driver issues or complicated virtualization setups. 

*Note: For our final production deployment on the university server, we will use an Ollama Docker container. However, your daily local workflow should remain native.*

---

## Step 1: Prerequisites
1. **Install Ollama**: Download and install Ollama natively for your OS from [ollama.com](https://ollama.com/) (Linux users can use the standard install script).
2. **Run the App**: Make sure the Ollama application is actively running in the background. You should see the Ollama icon in your system tray or menu bar.

---

## Step 2: The Modelfile
To guarantee the entire team uses the exact same model weights and quantization, we define our model using a `Modelfile` (very similar to a `Dockerfile`). We are using a **4-bit quantized version of the Qwen3 embedding model**. 

Create a file named `Modelfile` in the root of the project with exactly this line:

```dockerfile
FROM hf.co/Qwen/Qwen3-Embedding-4B-GGUF:Q8_0
```

---

## Step 3: Building the Model
Once you have installed Ollama and verify it is running, open your terminal in the root directory (where your Modelfile is) and run:

```bash
ollama create my-project-embed -f Modelfile
```

This command will download the specific quantized Qwen3 model from Hugging Face and tag it locally as `my-project-embed`.

---

## Step 4: Python Integration

Because we're standardizing on Ollama for local development, we use the lightweight, native `ollama` Python package to generate our embeddings asynchronously, adhering to our 100% Async I/O requirement.

Make sure your local `.env` file includes the correct configuration targeting the local instance:
```env
EMBEDDING_CLIENT_TYPE=ollama
OLLAMA_HOST=http://localhost:11434
OLLAMA_EMBED_MODEL=my-project-embed
```

Here is a clean example of how to connect to your natively-running Ollama setup using its async client:

```python
import asyncio
import ollama

async def test_embedding():
    # Initialize the async client pointing to the local Ollama instance
    # In the actual backend, this connection pool is cached and injected via dependencies.py
    client = ollama.AsyncClient(host="http://localhost:11434")

    text_to_embed = "This is a document we want to index in our vector database."

    # Generate the embedding
    response = await client.embeddings(
        model="my-project-embed", # Use the tag we created in Step 3
        prompt=text_to_embed
    )

    # Extract the vector
    vector = response["embedding"]

    print(f"Embedding dimensions: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")

if __name__ == "__main__":
    asyncio.run(test_embedding())
```

---

## Troubleshooting

- **Connection Refused**: If you get a connection error when your script tries to reach `http://localhost:11434`, the Ollama background service is not running. 
  - *Mac/Windows*: Open your Applications/programs and launch the Ollama app.
  - *Linux*: Start the service with `sudo systemctl start ollama`.
