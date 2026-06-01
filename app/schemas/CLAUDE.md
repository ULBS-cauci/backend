# Schema Dependency Map

This file tells a future agent **exactly which files to update** when any schema in this
directory is changed. Always read it before touching a schema.

---

## Dependency Matrix

| Schema file | What changed | Files that must also be updated |
|---|---|---|
| `chat_schemas.py` — `Message` | field added / renamed / removed | `scripts/seed.py` → `SEED_MESSAGES` dicts + `seed_messages()` |
| `chat_schemas.py` — `OutputFormat` | new lookup table added | `scripts/seed.py` → `SEED_OUTPUT_FORMATS`, `seed_output_formats()`, `_TRUNCATE_ORDER`, imports; `app/main.py` → startup imports |
| `chat_schemas.py` — `MessageCreate` | input DTO field changed | `app/api/routers/sessions.py` (if field is read directly); `scripts/seed.py` → `SEED_MESSAGES` |
| `admin_schemas.py` — `LlmTip` | field added / renamed / removed | `scripts/seed.py` → `SEED_LLM_TIPS` dicts + `seed_llm_tips()` |
| `admin_schemas.py` — `TipCategory` | new lookup table added | `scripts/seed.py` → `SEED_TIP_CATEGORIES`, `seed_tip_categories()`, `_TRUNCATE_ORDER`, imports; `app/main.py` → startup imports |
| `admin_schemas.py` — `SystemPrompt` | field added / renamed / removed | `scripts/seed.py` → `SEED_SYSTEM_PROMPTS` dicts + `seed_system_prompts()` |
| `user_schemas.py` — `User` / `UserRole` | field / enum value changed | `scripts/seed.py` → `SEED_USERS` dicts; `app/api/dependencies.py` → `get_current_user()` dummy user; `app/api/routers/auth.py` |
| `knowledge_schemas.py` — `Material` | field added / renamed / removed | `scripts/seed.py` → `seed_materials_mock()` (constructs `Material(...)` directly) |
| `course_schemas.py` — `Course` | field added / renamed / removed | `scripts/seed.py` → `SEED_COURSES` dicts; `app/services/course_service.py`; `app/api/routers/course.py` |
| `chat_schemas.py` — `Conversation` | field added / renamed / removed | `scripts/seed.py` → `SEED_CONVERSATIONS` dicts; `app/services/chat_service.py` |
| `chat_schemas.py` — `SharedLink` | field added / renamed / removed | `scripts/seed.py` → `SEED_SHARED_LINKS` dicts |
| Any `*` (`table=True`) model | **new table** | `app/main.py` → import list so `SQLModel.metadata.create_all` sees it on startup |
| Any `*` (`table=True`) model | **table dropped** | `app/main.py` → remove import; `scripts/seed.py` → remove from `_TRUNCATE_ORDER` and its seeder |

---

## Key File Locations

```
app/
├── main.py                          ← import every table=True model here (create_all)
├── api/
│   ├── dependencies.py              ← get_current_user(), hardcoded UUIDs
│   └── routers/
│       ├── sessions.py              ← uses MessageCreate, ConversationPublic, MessagePublic
│       ├── course.py                ← uses CourseCreate, CourseDisplay, MaterialPublic (also handles material upload/preview)
│       ├── auth.py                  ← uses UserCreate, UserPublic, UserRole
│       └── admin.py                 ← uses SystemPromptPublic, LlmTipPublic (stub router)
├── services/
│   ├── chat_service.py              ← constructs Message() / Conversation() directly
│   ├── course_service.py            ← queries Course
│   └── file_service.py              ← constructs Material() directly
└── schemas/                         ← YOU ARE HERE
    ├── user_schemas.py              ← User, UserRole, UserCreate, UserPublic
    ├── course_schemas.py            ← Course, CourseCreate, CourseDisplay
    ├── knowledge_schemas.py         ← Material, MaterialCreate, MaterialPublic
    ├── chat_schemas.py              ← OutputFormat, Conversation, Message, Attachment,
    │                                   SharedLink + their DTOs; MessageSender enum
    ├── admin_schemas.py             ← TipCategory, SystemPrompt, LlmTip + their DTOs
    ├── llm_schemas.py               ← ChatMessage, MessageRole (LLM wire format — not DB)
    ├── vector_schemas.py            ← Qdrant payload schemas
    └── time_schema.py               ← TimestampSchema, TimeSchema mixins

scripts/
└── seed.py                          ← DB seeder; mirrors every table model
    ├── SeedIDs                      ← fixed UUIDs for idempotency
    ├── _TRUNCATE_ORDER              ← reverse-FK order for --reset
    ├── SEED_* constants             ← one list per table
    ├── seed_*() functions           ← one function per table
    └── run_seed()                   ← orchestrator — FK-safe call order
```

---

## Rules for Future Agents

1. **Renaming a field** — change the schema class AND every `SEED_*` dict key in
   `scripts/seed.py` that sets that field. Search with:
   `grep -rn "<old_field_name>" backend/app backend/scripts`

2. **Adding a new table** — follow this checklist:
   - [ ] Create `*Base`, `*` (table=True), `*Create`, `*Public` in the appropriate schema file
   - [ ] Import it in `app/main.py` (triggers `create_all`)
   - [ ] Add it to `_TRUNCATE_ORDER` in `scripts/seed.py` (correct FK position)
   - [ ] Add `SEED_<TABLE>` data constant in `scripts/seed.py`
   - [ ] Add `seed_<table>()` function in `scripts/seed.py`
   - [ ] Call `seed_<table>()` in `run_seed()` before any table that FK-references it

3. **Lookup / reference tables** (no FK parents, referenced by others) — seed them
   **first** in `run_seed()`, before the tables that point to them.

4. **Dropping a table** — reverse the checklist above; also check all routers and
   services for any `.get()` / `select()` queries against the removed model.

5. **Changing an enum** (`UserRole`, `MessageSender`) — update the enum class, then
   search for all call sites that construct instances with the old value (seed data,
   services, tests).
