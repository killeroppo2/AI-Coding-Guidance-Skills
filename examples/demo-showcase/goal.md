# Goal: Build a URL Shortener CLI with SQLite Backend

Build a command-line URL shortener that stores mappings in a local SQLite database.

## Requirements
- Accept a long URL and generate a unique short code
- Store URL mappings in a SQLite database (urls.db)
- Lookup original URL by short code
- List all stored URL mappings with creation timestamps
- Delete expired URLs (older than configurable TTL)
- Handle duplicate URLs gracefully (return existing short code)
