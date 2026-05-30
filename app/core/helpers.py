import os
import uuid


def build_material_object_key(course_id: uuid.UUID, material_id: uuid.UUID, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"materials/{course_id}/{material_id}{ext}"


def build_attachment_object_key(user_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return f"attachments/{user_id}/{attachment_id}{ext}"
