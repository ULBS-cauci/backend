# Database Schema

This document contains the Entity-Relationship mapping for the local PostgreSQL database, generated from the underlying SQLModel implementation.

```mermaid
erDiagram
    %% 0. Lookup / Reference Tables
    output_formats {
        UUID id PK
        string name UK
        string description
        datetime created_at
    }

    tip_categories {
        UUID id PK
        string name UK
        datetime created_at
    }

    %% 1. Identity & Courses
    users {
        UUID id PK
        string email UK
        string first_name
        string last_name
        enum role "Student, Professor, Admin"
        string hashed_password
        datetime created_at
        datetime updated_at
    }

    courses {
        UUID id PK
        string title
        string description
        UUID held_by FK "Ref: users.id"
        datetime created_at
        datetime updated_at
    }

    %% 2. Knowledge Base
    materials {
        UUID id PK
        UUID course_id FK "Ref: courses.id"
        UUID uploaded_by FK "Ref: users.id"
        string file_name
        string file_type
        string vector_namespace
        string object_storage_key
        datetime created_at
    }

    %% 3. Chat System
    conversations {
        UUID id PK
        UUID user_id FK "Ref: users.id"
        UUID course_id FK "Ref: courses.id"
        string title
        datetime created_at
        datetime updated_at
    }

    messages {
        UUID id PK
        UUID conversation_id FK "Ref: conversations.id"
        enum sender "User, System, AI"
        text content
        UUID output_format_id FK "Ref: output_formats.id"
        datetime created_at
    }

    attachments {
        UUID id PK
        UUID user_id FK "Ref: users.id"
        UUID message_id FK "Ref: messages.id (nullable)"
        string file_name
        string object_storage_key
        datetime created_at
    }

    shared_links {
        UUID id PK
        UUID conversation_id FK "Ref: conversations.id"
        string token UK
        datetime expires_at
        datetime created_at
    }

    %% 4. Configuration & Prompts
    system_prompts {
        UUID id PK
        UUID author_id FK "Ref: users.id"
        string title
        text content
        datetime created_at
    }

    llm_tips {
        UUID id PK
        UUID category_id FK "Ref: tip_categories.id"
        string title
        text description
        text example_prompt
        datetime created_at
    }

    %% Relationships
    %% Identity & Setup
    users ||--o{ courses : "held_by"
    users ||--o{ materials : "uploaded_by"
    users ||--o{ conversations : "participates_in"
    users ||--o{ system_prompts : "authored_by"
    users ||--o{ attachments : "owns"

    %% Course Data
    courses ||--o{ materials : "contains"
    courses ||--o{ conversations : "context_for"

    %% Chat System
    conversations ||--o{ messages : "contains"
    conversations ||--o| shared_links : "generates"
    messages ||--o{ attachments : "includes"
    messages }o--o| output_formats : "requested_format"

    %% Tips
    tip_categories ||--o{ llm_tips : "categorises"
```

## Class Diagram

This diagram visualizes the Object-Oriented mapping used by SQLModel (and FastAPI schemas) in the codebase.

```mermaid
classDiagram
    class OutputFormat {
        +UUID id
        +String name
        +String description
        +DateTime created_at
    }

    class TipCategory {
        +UUID id
        +String name
        +DateTime created_at
    }

    class User {
        +UUID id
        +String email
        +String first_name
        +String last_name
        +UserRole role
        +String hashed_password
        +DateTime created_at
        +DateTime updated_at
    }

    class Course {
        +UUID id
        +UUID held_by
        +String title
        +String description
        +DateTime created_at
        +DateTime updated_at
    }

    class Material {
        +UUID id
        +UUID course_id
        +UUID uploaded_by
        +String file_name
        +String file_type
        +String vector_namespace
        +String object_storage_key
        +DateTime created_at
    }

    class Conversation {
        +UUID id
        +UUID user_id
        +UUID course_id
        +String title
        +DateTime created_at
        +DateTime updated_at
    }

    class Message {
        +UUID id
        +UUID conversation_id
        +MessageSender sender
        +Text content
        +UUID output_format_id
        +DateTime created_at
    }

    class Attachment {
        +UUID id
        +UUID user_id
        +UUID message_id
        +String file_name
        +String object_storage_key
        +DateTime created_at
    }

    class SharedLink {
        +UUID id
        +UUID conversation_id
        +String token
        +DateTime expires_at
        +DateTime created_at
    }

    class SystemPrompt {
        +UUID id
        +UUID author_id
        +String title
        +Text content
        +DateTime created_at
    }

    class LlmTip {
        +UUID id
        +UUID category_id
        +String title
        +Text description
        +Text example_prompt
        +DateTime created_at
    }

    %% Relationships as Class Dependencies / Composition
    User "1" --> "*" Course : creates
    User "1" --> "*" SystemPrompt : authors
    User "1" --> "*" Material : uploads
    User "1" --> "*" Conversation : participates
    User "1" --> "*" Attachment : owns

    Course "1" *-- "*" Material : contains
    Course "1" <-- "*" Conversation : references

    Conversation "1" *-- "*" Message : owns
    Conversation "1" *-- "0..1" SharedLink : generates

    Message "1" *-- "*" Attachment : includes
    Message "*" --> "0..1" OutputFormat : requests

    TipCategory "1" *-- "*" LlmTip : categorises
```

## Object Diagram (Example State)

This diagram shows a sample instantiation of the models at a specific point in time to visualize the relationships in action.

```mermaid
classDiagram
    %% Object Instances
    class professor_john {
        <<User>>
        id: 7f1a3b10...
        first_name: "John"
        role: "Professor"
    }

    class student_jane {
        <<User>>
        id: 4b29c122...
        first_name: "Jane"
        role: "Student"
    }

    class ai_course {
        <<Course>>
        id: c382901a...
        title: "Introduction to AI"
        held_by: 7f1a3b10...
    }

    class lecture_slides {
        <<Material>>
        id: 9d123bca...
        file_name: "lecture1.pdf"
        uploaded_by: 7f1a3b10...
        course_id: c382901a...
    }

    class jane_conversation {
        <<Conversation>>
        id: 11eeb229...
        title: "Doubt regarding Lecture 1"
        user_id: 4b29c122...
        course_id: c382901a...
    }

    class current_message {
        <<Message>>
        id: 28bc9910...
        conversation_id: 11eeb229...
        sender: "User"
        content: "Can you explain backpropagation?"
        output_format_id: null
    }

    class user_attachment {
        <<Attachment>>
        id: 39de18cc...
        user_id: 4b29c122...
        message_id: 28bc9910...
        file_name: "my_notes.docx"
    }

    class markdown_format {
        <<OutputFormat>>
        id: a1b2c3d4...
        name: "markdown"
        description: "Render response as Markdown"
    }

    class general_tips {
        <<TipCategory>>
        id: f9e8d7c6...
        name: "General"
    }

    %% Object Links
    professor_john ..> ai_course : creates
    professor_john ..> lecture_slides : uploads
    ai_course *-- lecture_slides : contains

    student_jane ..> jane_conversation : participates
    jane_conversation ..> ai_course : context

    jane_conversation *-- current_message : owns
    current_message *-- user_attachment : contains
    current_message ..> markdown_format : requests
```
