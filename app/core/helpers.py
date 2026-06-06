import os
import uuid


# Single source of truth for mapping a supported file extension to its MIME type.
# Used when storing objects in MinIO and when serving them back for inline preview.
CONTENT_TYPE_BY_EXTENSION: dict[str, str] = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
}


def content_type_for_filename(filename: str) -> str:
    """Resolve a filename's MIME type from its extension, defaulting to octet-stream."""
    suffix = os.path.splitext(filename)[1].lstrip(".").lower()
    return CONTENT_TYPE_BY_EXTENSION.get(suffix, "application/octet-stream")


def build_material_object_key(course_id: uuid.UUID, material_id: uuid.UUID, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"materials/{course_id}/{material_id}{ext}"


def build_attachment_object_key(user_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"attachments/{user_id}/{attachment_id}{ext}"
