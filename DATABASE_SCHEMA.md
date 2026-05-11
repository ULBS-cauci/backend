# Database Schema

This document contains the Entity-Relationship mapping for the local PostgreSQL database, generated from the underlying SQLModel implementation.

```mermaid
erDiagram
    %% Identity & Courses
    users {
        UUID id PK
        string email UK
        string first_name
        string last_name
        string role "Student, Professor, Admin"
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

    %% Knowledge Base
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

    %% Chat System
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
        string sender "User, System, AI"
        string content
        string output_type_requested
        datetime created_at
    }

    attachments {
        UUID id PK
        UUID message_id FK "Ref: messages.id"
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

    %% Configuration & Preferences
    system_prompts {
        UUID id PK
        UUID author_id FK "Ref: users.id"
        string title
        string content
        datetime created_at
    }

    llm_tips {
        UUID id PK
        string title
        string description
        string example_prompt
        string category
        datetime created_at
    }

    %% Relationships (Restructured for better layout)
    %% Identity & Setup
    users ||--o{ courses : "creates"
    
    %% Course Data
    courses ||--o{ materials : "contains"
    materials }o--|| users : "uploaded_by"
    
    system_prompts }o--|| users : "authored_by"

    %% Chat System Sub-graph
    courses ||--o{ conversations : "context_for"
    users ||--o{ conversations : "participates_in"
    
    conversations ||--o{ messages : "contains"
    conversations ||--o| shared_links : "generates"
    messages ||--o{ attachments : "includes"
```

## Class Diagram

This diagram visualizes the Object-Oriented mapping used by SQLModel (and FastAPI schemas) in the codebase.

```mermaid
classDiagram
    class User {
        +UUID id
        +String email
        +String first_name
        +String last_name
        +String role
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
        +String sender
        +String content
        +String output_type_requested
        +DateTime created_at
    }

    class Attachment {
        +UUID id
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
        +String content
        +DateTime created_at
    }

    class LlmTip {
        +UUID id
        +String title
        +String description
        +String example_prompt
        +String category
        +DateTime created_at
    }

    %% Relationships as Class Dependencies / Composition
    User "1" --> "*" Course : creates
    User "1" --> "*" SystemPrompt : authors
    User "1" --> "*" Material : uploads
    User "1" --> "*" Conversation : participates 
    
    Course "1" *-- "*" Material : contains
    Course "1" *-- "*" SystemPrompt : configures
    Course "1" <-- "*" Conversation : references
    n "1" *-- "*" Message : owns
    Conversation "1" *-- "0..1" SharedLink : generates
    
    Message "1" *-- "*" Attachment : includes
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
        created_by: 7f1a3b10...
    }
hel
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
    }

    class user_attachment {
        <<Attachment>>
        id: 39de18cc...
        message_id: 28bc9910...
        file_name: "my_notes.docx"
    }

    %% Object Links
    professor_john ..> ai_course : creates
    professor_john ..> lecture_slides : uploads
    ai_course *-- lecture_slides : contains
    
    student_jane ..> jane_conversation : participates
    jane_conversation ..> ai_course : context
    
    jane_conversation *-- current_message : owns
    current_message *-- user_attachment : contains
```