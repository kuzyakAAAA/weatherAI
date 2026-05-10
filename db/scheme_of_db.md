```mermaid
erDiagram

    USERS {
        BIGINT user_id PK
        TEXT style
        TEXT preferred_city
        TIMESTAMP created_at
    }

    HISTORY {
        SERIAL id PK
        BIGINT user_id FK
        TEXT city
        TEXT weather_json
        TEXT advice
        TIMESTAMP timestamp
    }

    USERS ||--o{ HISTORY : "has"
```