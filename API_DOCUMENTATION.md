# NCII Shield API Documentation

## Base URL
```
http://localhost:8000
```

## API Endpoints

### 1. Create Case
**POST** `/cases/`

Creates a new case for a victim.

```json
{
  "victim_id": "string",
  "authorization_doc": "string (optional)"
}
```

Response:
```json
{
  "id": 1,
  "victim_id": "victim123",
  "status": "active",
  "created_at": "2024-04-24T00:00:00Z",
  "authorization_doc": "Authorization document reference"
}
```

### 2. List Cases
**GET** `/cases/`

Lists all cases with pagination support.

Query Parameters:
- `skip`: Number of records to skip (default: 0)
- `limit`: Maximum records to return (default: 100)

Response:
```json
{
  "cases": [
    {
      "id": 1,
      "victim_id": "victim123",
      "status": "active",
      "created_at": "2024-04-24T00:00:00Z",
      "authorization_doc": "Authorization document reference"
    }
  ],
  "total": 1
}
```

### 3. Get Case by ID
**GET** `/cases/{case_id}`

Retrieves a specific case.

Response: Same as Create Case

### 4. Add Identifier
**POST** `/cases/{case_id}/identifiers`

Adds an identifier to a case.

```json
{
  "type": "name|handle|alias|email|phone",
  "value": "string"
}
```

Response:
```json
{
  "id": 1,
  "case_id": 1,
  "type": "name",
  "value": "John Doe",
  "created_at": "2024-04-24T00:00:00Z"
}
```

### 5. Add Reference Hash
**POST** `/cases/{case_id}/reference-hashes`

Adds a client-side computed hash to a case.

```json
{
  "phash": 9223372036854775807,
  "dhash": 1234567890123456789,
  "face_embedding": [0.1, 0.2, ...],  // 128-dimensional array (optional)
  "label": "string (optional)"
}
```

Response:
```json
{
  "id": 1,
  "case_id": 1,
  "phash": 9223372036854775807,
  "dhash": 1234567890123456789,
  "face_embedding": [0.1, 0.2, ...],
  "label": "Reference image 1",
  "created_at": "2024-04-24T00:00:00Z"
}
```

### 6. Add Target URL
**POST** `/cases/{case_id}/targets`

Manually adds a target URL to investigate.

```json
{
  "url": "https://example.com/page",
  "discovery_source": "manual",
  "confidence_score": 0.95
}
```

Response:
```json
{
  "id": 1,
  "case_id": 1,
  "url": "https://example.com/page",
  "status": "discovered",
  "discovery_source": "manual",
  "confidence_score": 0.95,
  "next_action_at": null,
  "created_at": "2024-04-24T00:00:00Z",
  "updated_at": "2024-04-24T00:00:00Z"
}
```

## Sample CURL Commands

### Create a Case
```bash
curl -X POST http://localhost:8000/cases/ \
  -H "Content-Type: application/json" \
  -d '{
    "victim_id": "victim123",
    "authorization_doc": "Authorized by victim on 2024-04-24"
  }'
```

### Add Identifiers
```bash
# Add a name
curl -X POST http://localhost:8000/cases/1/identifiers \
  -H "Content-Type: application/json" \
  -d '{
    "type": "name",
    "value": "John Doe"
  }'

# Add a handle
curl -X POST http://localhost:8000/cases/1/identifiers \
  -H "Content-Type: application/json" \
  -d '{
    "type": "handle",
    "value": "@johndoe"
  }'
```

### Add Reference Hashes
```bash
curl -X POST http://localhost:8000/cases/1/reference-hashes \
  -H "Content-Type: application/json" \
  -d '{
    "phash": 9223372036854775807,
    "dhash": 1234567890123456789,
    "face_embedding": null,
    "label": "Reference image 1"
  }'
```

### Add Target URL
```bash
curl -X POST http://localhost:8000/cases/1/targets \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/suspicious-page",
    "discovery_source": "manual"
  }'
```

### Full Case Creation Flow
```bash
# 1. Create case
CASE_ID=$(curl -s -X POST http://localhost:8000/cases/ \
  -H "Content-Type: application/json" \
  -d '{"victim_id": "victim123"}' | jq -r '.id')

echo "Created case ID: $CASE_ID"

# 2. Add identifiers
curl -X POST http://localhost:8000/cases/$CASE_ID/identifiers \
  -H "Content-Type: application/json" \
  -d '{"type": "name", "value": "Test User"}'

# 3. Add reference hash (simulated)
curl -X POST http://localhost:8000/cases/$CASE_ID/reference-hashes \
  -H "Content-Type: application/json" \
  -d '{
    "phash": 123456789,
    "dhash": 987654321,
    "label": "Test hash"
  }'

# 4. Add target
curl -X POST http://localhost:8000/cases/$CASE_ID/targets \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/test"}'

# 5. View the case
curl http://localhost:8000/cases/$CASE_ID
```

## Interactive API Documentation

When the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These provide interactive API exploration and testing interfaces.

## Audit Trail

All operations create entries in the `audit_log` table:
- Case creation
- Identifier additions
- Reference hash registrations
- Target URL additions

The audit log is append-only and enforced at the database level.