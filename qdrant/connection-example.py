import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http import models

load_dotenv()


def build_client() -> QdrantClient:
    qdrant_url = os.getenv("QDRANT_URL", "")
    qdrant_port = os.getenv("QDRANT_PORT", "6333")
    qdrant_api_key = os.getenv("QDRANT_SERVICE_API_KEY")

    if qdrant_url.startswith(("http://", "https://")):
        return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    return QdrantClient(
        host=qdrant_url,
        port=int(qdrant_port),
        api_key=qdrant_api_key,
    )


client = build_client()


def search_points(
    collection_name: str,
    query_vector: list[float],
    limit: int = 2,
):
    """Run similarity search across qdrant-client versions."""
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return response.points

    return client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )

### Test connection by listing collections
# print(client.get_collections())


### Create a collection
# collection_name = "test_collection"
# try:
#     client.recreate_collection(
#         collection_name=collection_name,
#         vectors_config=models.VectorParams(
#           size=128,
#           distance=models.Distance.COSINE),
#     )
#     print(f"Collection '{collection_name}' created successfully.")
# except Exception as e:
#     print(f"Error creating collection: {e}")


### Remove a collection
# collection_name = "test_collection"
# try:
#     client.delete_collection(collection_name=collection_name)
#     print(f"Collection '{collection_name}' deleted successfully.")
# except Exception as e:
#     print(f"Error deleting collection: {e}")



### Store embeddings in a collection
# collection_name = "test_collection"
# vector_size = 4

# client.recreate_collection(
#     collection_name=collection_name,
#     vectors_config=models.VectorParams(
#         size=vector_size,
#         distance=models.Distance.COSINE,
#     ),
# )

# points = [
#     models.PointStruct(
#         id=1,
#         vector=[0.1, 0.2, 0.3, 0.4],
#         payload={"book_id": "book_1", "title": "Example Book One"},
#     ),
#     models.PointStruct(
#         id=2,
#         vector=[0.4, 0.3, 0.2, 0.1],
#         payload={"book_id": "book_2", "title": "Example Book Two"},
#     ),
# ]

# client.upsert(collection_name=collection_name, points=points)

# print("Inserted 2 points into collection:", collection_name)


### Search for similar vectors
# collection_name = "test_collection"
# query_vector = [0.1, 0.2, 0.3, 0.4]
# search_results = search_points(
#     collection_name=collection_name,
#     query_vector=query_vector,
#     limit=2,
# )
# print("Search results:" )
# for result in search_results:
#     title = (result.payload or {}).get("title", "<no title>")
#     print(f"  - {title} (ID: {result.id})")