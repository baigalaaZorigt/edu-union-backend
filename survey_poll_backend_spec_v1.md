# Survey / Poll Backend Specification — V1

## 1. Scope

Энэ backend-ийн зорилго нь:

- Админ судалгаа / санал асуулга үүсгэх
- Асуултууд нэмэх
- Асуултын төрлүүд сонгох
- Сонголтууд нэмэх
- Portal дээр хэрэглэгч судалгаа бөглөх
- Хэрэглэгчийн хариултыг хадгалах
- Admin дээр үр дүнг тоо, хувь, графикаар харах
- Санал асуулгад PDF файл холбох

V1 хувилбарт дараах зүйлс **шаардлагагүй**:

- Anonymous voting
- IP / device duplicate prevention
- Conditional logic
- Skip logic
- Published survey versioning
- Complex form branching
- Advanced survey workflow

---

# 2. Main Concept

Survey болон Poll-ийг тусдаа backend систем болгохгүй.

Нэг `forms` engine ашиглана.

```text
forms.type = survey
forms.type = poll
```

## Survey

```text
Багшийн ажлын ачааллын судалгаа
```

## Poll

```text
Хуулийн төсөлд санал авах
```

Poll төрлийн form дээр PDF файл холбож болно.

---

# 3. Database Structure

Үндсэн хүснэгтүүд:

```text
forms
form_questions
form_options
form_submissions
form_answers
form_answer_options
form_documents
```

Relation:

```text
forms
 │
 ├── form_questions
 │       │
 │       └── form_options
 │
 ├── form_documents
 │
 └── form_submissions
         │
         └── form_answers
                 │
                 └── form_answer_options
```

---

# 4. forms

Survey / Poll-ийн үндсэн мэдээлэл.

```sql
CREATE TABLE forms (
    id BIGSERIAL PRIMARY KEY,

    type VARCHAR(20) NOT NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT,

    status VARCHAR(20) NOT NULL DEFAULT 'draft',

    start_at TIMESTAMP NULL,
    end_at TIMESTAMP NULL,

    show_results BOOLEAN NOT NULL DEFAULT TRUE,
    one_response BOOLEAN NOT NULL DEFAULT TRUE,

    created_by BIGINT NULL,
    updated_by BIGINT NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NULL,
    deleted_at TIMESTAMP NULL
);
```

## type

```text
survey
poll
```

## status

```text
draft
published
closed
```

---

# 5. form_questions

Form-ийн асуултууд.

```sql
CREATE TABLE form_questions (
    id BIGSERIAL PRIMARY KEY,

    form_id BIGINT NOT NULL,

    question_type VARCHAR(30) NOT NULL,

    title TEXT NOT NULL,
    description TEXT,

    is_required BOOLEAN NOT NULL DEFAULT FALSE,

    sort_order INTEGER NOT NULL DEFAULT 0,

    settings JSONB NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NULL,

    CONSTRAINT fk_form_questions_form
        FOREIGN KEY (form_id)
        REFERENCES forms(id)
        ON DELETE CASCADE
);
```

---

# 6. Question Types

V1 дээр дараах 4 төрөл хангалттай.

```text
single_choice
multiple_choice
scale
open_text
```

---

## 6.1 Single Choice

Жишээ:

```text
Та ажлын ачааллаа хэрхэн үнэлэх вэ?

○ Хэт их
○ Боломжийн
○ Бага
```

---

## 6.2 Multiple Choice

```text
Аль сургалтад хамрагдах хүсэлтэй вэ?

☐ Заах арга зүй
☐ Дижитал технологи
☐ Сэтгэл зүй
```

---

## 6.3 Scale

```text
Үйлчилгээг 1-5 хүртэл үнэлнэ үү.

1 2 3 4 5
```

`settings`:

```json
{
  "min": 1,
  "max": 5
}
```

---

## 6.4 Open Text

```text
Нэмэлт санал хүсэлт

[ textarea ]
```

---

# 7. form_options

Single choice болон Multiple choice асуултын сонголтууд.

```sql
CREATE TABLE form_options (
    id BIGSERIAL PRIMARY KEY,

    question_id BIGINT NOT NULL,

    label VARCHAR(500) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NULL,

    CONSTRAINT fk_form_options_question
        FOREIGN KEY (question_id)
        REFERENCES form_questions(id)
        ON DELETE CASCADE
);
```

Жишээ:

```text
Question:
Та ажлын ачааллаа хэрхэн үнэлэх вэ?

Options:

1. Хэт их
2. Боломжийн
3. Бага
```

---

# 8. form_documents

Poll дээр PDF файл холбох.

```sql
CREATE TABLE form_documents (
    id BIGSERIAL PRIMARY KEY,

    form_id BIGINT NOT NULL,

    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    mime_type VARCHAR(100),
    file_size BIGINT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_form_documents_form
        FOREIGN KEY (form_id)
        REFERENCES forms(id)
        ON DELETE CASCADE
);
```

Жишээ:

```text
labor-law-2026.pdf
```

Portal дээр:

```text
PDF Viewer

↓

Санал өгөх form
```

байдлаар харуулна.

---

# 9. form_submissions

Нэг хэрэглэгчийн нэг form-д өгсөн submission.

```sql
CREATE TABLE form_submissions (
    id BIGSERIAL PRIMARY KEY,

    form_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,

    submitted_at TIMESTAMP NOT NULL DEFAULT NOW(),

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_form_submissions_form
        FOREIGN KEY (form_id)
        REFERENCES forms(id)
        ON DELETE CASCADE
);
```

Нэг хэрэглэгч нэг удаа бөглөх requirement байгаа бол:

```sql
CREATE UNIQUE INDEX ux_form_submission_user
ON form_submissions(form_id, user_id);
```

---

# 10. form_answers

Асуултын хариулт.

```sql
CREATE TABLE form_answers (
    id BIGSERIAL PRIMARY KEY,

    submission_id BIGINT NOT NULL,
    question_id BIGINT NOT NULL,

    text_value TEXT NULL,
    numeric_value NUMERIC NULL,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_form_answers_submission
        FOREIGN KEY (submission_id)
        REFERENCES form_submissions(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_form_answers_question
        FOREIGN KEY (question_id)
        REFERENCES form_questions(id)
        ON DELETE CASCADE
);
```

---

# 11. form_answer_options

Single choice / Multiple choice-ийн сонгосон option.

```sql
CREATE TABLE form_answer_options (
    id BIGSERIAL PRIMARY KEY,

    answer_id BIGINT NOT NULL,
    option_id BIGINT NOT NULL,

    CONSTRAINT fk_answer_option_answer
        FOREIGN KEY (answer_id)
        REFERENCES form_answers(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_answer_option_option
        FOREIGN KEY (option_id)
        REFERENCES form_options(id)
        ON DELETE CASCADE
);
```

---

# 12. Answer Storage Examples

## Single Choice

```text
form_answers

question_id = 1
```

```text
form_answer_options

option_id = 10
```

---

## Multiple Choice

```text
form_answers

question_id = 2
```

```text
form_answer_options

option_id = 21
option_id = 22
option_id = 25
```

---

## Scale

```text
form_answers

question_id = 3
numeric_value = 4
```

---

## Open Text

```text
form_answers

question_id = 4
text_value = "Сургалтын тоог нэмэх хэрэгтэй."
```

---

# 13. Admin API

## Form List

```http
GET /api/admin/forms
```

Query:

```text
type=survey
status=published
search=...
page=1
per_page=20
```

---

## Form Detail

```http
GET /api/admin/forms/{id}
```

---

## Create Form

```http
POST /api/admin/forms
```

Example:

```json
{
  "type": "survey",
  "title": "Багшийн ажлын ачааллын судалгаа 2026",
  "description": "Багш нарын ажлын ачааллыг үнэлэх",
  "start_at": "2026-08-15 00:00:00",
  "end_at": "2026-09-15 23:59:59",
  "show_results": true,
  "one_response": true
}
```

---

## Update Form

```http
PUT /api/admin/forms/{id}
```

---

## Delete Form

```http
DELETE /api/admin/forms/{id}
```

---

## Publish

```http
POST /api/admin/forms/{id}/publish
```

---

## Close

```http
POST /api/admin/forms/{id}/close
```

---

# 14. Question Builder API

## Add Question

```http
POST /api/admin/forms/{formId}/questions
```

Example:

```json
{
  "question_type": "single_choice",
  "title": "Та ажлын ачааллаа хэрхэн үнэлэх вэ?",
  "is_required": true,
  "sort_order": 1,
  "options": [
    {
      "label": "Хэт их"
    },
    {
      "label": "Боломжийн"
    },
    {
      "label": "Бага"
    }
  ]
}
```

---

## Update Question

```http
PUT /api/admin/questions/{id}
```

---

## Delete Question

```http
DELETE /api/admin/questions/{id}
```

---

## Duplicate Question

Optional mockup feature:

```http
POST /api/admin/questions/{id}/duplicate
```

---

## Reorder Questions

```http
POST /api/admin/forms/{formId}/questions/reorder
```

Request:

```json
{
  "questions": [
    {
      "id": 10,
      "sort_order": 1
    },
    {
      "id": 15,
      "sort_order": 2
    },
    {
      "id": 17,
      "sort_order": 3
    }
  ]
}
```

---

# 15. PDF Upload API

Poll form дээр PDF upload хийх.

```http
POST /api/admin/forms/{formId}/document
```

Request:

```text
multipart/form-data
```

Field:

```text
file
```

Validation:

```text
mime type: application/pdf
max size: project requirement-аар
```

---

# 16. Portal API

## Survey List

```http
GET /api/portal/forms?type=survey
```

---

## Poll List

```http
GET /api/portal/forms?type=poll
```

---

## Form Detail

```http
GET /api/portal/forms/{id}
```

Response example:

```json
{
  "id": 10,
  "type": "survey",
  "title": "Багшийн ажлын ачааллын судалгаа 2026",
  "description": "Судалгааны тайлбар",
  "start_at": "2026-08-15",
  "end_at": "2026-09-15",
  "has_submitted": false,
  "questions": [
    {
      "id": 101,
      "question_type": "single_choice",
      "title": "Та ажлын ачааллаа хэрхэн үнэлэх вэ?",
      "is_required": true,
      "options": [
        {
          "id": 1001,
          "label": "Хэт их"
        },
        {
          "id": 1002,
          "label": "Боломжийн"
        },
        {
          "id": 1003,
          "label": "Бага"
        }
      ]
    }
  ]
}
```

---

# 17. Submit Survey / Poll

```http
POST /api/portal/forms/{id}/submit
```

Request:

```json
{
  "answers": [
    {
      "question_id": 101,
      "option_ids": [1001]
    },
    {
      "question_id": 102,
      "option_ids": [1005, 1006]
    },
    {
      "question_id": 103,
      "numeric_value": 4
    },
    {
      "question_id": 104,
      "text_value": "Сургалтын боломжийг нэмэгдүүлэх хэрэгтэй."
    }
  ]
}
```

Response:

```json
{
  "status": true,
  "message": "Таны санал бүртгэгдлээ."
}
```

---

# 18. Submit Validation

Backend submit хийх үед дараах validation хангалттай.

```text
Form exists
    ↓
Form status = published
    ↓
Current date >= start_at
    ↓
Current date <= end_at
    ↓
User өмнө submit хийсэн эсэх
    ↓
Required questions answered
    ↓
Question тухайн form-д хамаарах эсэх
    ↓
Option тухайн question-д хамаарах эсэх
    ↓
Answer type зөв эсэх
    ↓
Save submission
    ↓
Save answers
```

Submission болон answers save хийхдээ transaction ашиглана.

---

# 19. Admin Result API

Admin дээр үр дүн харах үндсэн endpoint.

```http
GET /api/admin/forms/{id}/results
```

Response example:

```json
{
  "form_id": 10,
  "total_responses": 300,
  "questions": [
    {
      "question_id": 101,
      "title": "Та ажлын ачааллаа хэрхэн үнэлэх вэ?",
      "question_type": "single_choice",
      "results": [
        {
          "option_id": 1001,
          "label": "Хэт их",
          "count": 120,
          "percent": 40
        },
        {
          "option_id": 1002,
          "label": "Боломжийн",
          "count": 90,
          "percent": 30
        },
        {
          "option_id": 1003,
          "label": "Бага",
          "count": 90,
          "percent": 30
        }
      ]
    }
  ]
}
```

Frontend үүгээр:

```text
Bar chart
Pie chart
Donut chart
Percentage list
```

харуулж болно.

---

# 20. Scale Result

Scale question:

```text
1 2 3 4 5
```

Admin result:

```json
{
  "question_id": 103,
  "question_type": "scale",
  "average": 4.2,
  "total": 300,
  "results": [
    {
      "value": 1,
      "count": 5
    },
    {
      "value": 2,
      "count": 10
    },
    {
      "value": 3,
      "count": 35
    },
    {
      "value": 4,
      "count": 120
    },
    {
      "value": 5,
      "count": 130
    }
  ]
}
```

---

# 21. Open Text Result

Open text result-д graph шаардлагагүй.

```http
GET /api/admin/forms/{id}/questions/{questionId}/answers
```

Response:

```json
{
  "question_id": 104,
  "answers": [
    {
      "id": 1,
      "text": "Сургалтын тоог нэмэх хэрэгтэй.",
      "submitted_at": "2026-08-12 10:20:00"
    },
    {
      "id": 2,
      "text": "Цагийн хуваарийг сайжруулах хэрэгтэй.",
      "submitted_at": "2026-08-12 10:24:00"
    }
  ]
}
```

---

# 22. Result Trend

Хэрэв admin dashboard дээр өдөр бүрийн response graph хэрэгтэй бол:

```http
GET /api/admin/forms/{id}/results/trend
```

SQL:

```sql
SELECT
    DATE(submitted_at) AS date,
    COUNT(*) AS total
FROM form_submissions
WHERE form_id = :form_id
GROUP BY DATE(submitted_at)
ORDER BY date;
```

Response:

```json
{
  "items": [
    {
      "date": "2026-08-10",
      "total": 30
    },
    {
      "date": "2026-08-11",
      "total": 45
    },
    {
      "date": "2026-08-12",
      "total": 70
    }
  ]
}
```

---

# 23. Laravel Suggested Structure

```text
app/

Models/
    Form.php
    FormQuestion.php
    FormOption.php
    FormSubmission.php
    FormAnswer.php
    FormAnswerOption.php
    FormDocument.php

Http/
    Controllers/

        Admin/
            FormController.php
            FormQuestionController.php
            FormResultController.php

        Portal/
            FormController.php
            FormSubmissionController.php

    Requests/
        StoreFormRequest.php
        UpdateFormRequest.php
        StoreQuestionRequest.php
        SubmitFormRequest.php

Services/
    FormService.php
    FormSubmissionService.php
    FormResultService.php
```

---

# 24. Service Responsibilities

## FormService

```text
Create form
Update form
Delete form
Publish form
Close form
```

## FormSubmissionService

```text
Validate submission
Create submission
Save answers
```

## FormResultService

```text
Total responses
Option counts
Percentages
Scale average
Trend data
```

---

# 25. Recommended V1 Features

| Feature | V1 |
|---|---|
| Survey create/edit/delete | ✅ |
| Poll create/edit/delete | ✅ |
| Question builder | ✅ |
| Single choice | ✅ |
| Multiple choice | ✅ |
| Scale | ✅ |
| Open text | ✅ |
| Required question | ✅ |
| Question reorder | ✅ |
| Question duplicate | ✅ |
| PDF upload for poll | ✅ |
| Portal survey list | ✅ |
| Portal poll list | ✅ |
| Survey submit | ✅ |
| Poll submit | ✅ |
| One user one response | ✅ |
| Admin result count | ✅ |
| Admin percentage | ✅ |
| Bar / Pie / Donut graph data | ✅ |
| Simple daily trend | ✅ |
| Anonymous voting | ❌ |
| IP/device prevention | ❌ |
| Conditional logic | ❌ |
| Skip logic | ❌ |
| Form versioning | ❌ |
| Complex workflow | ❌ |

---

# 26. Backend Complexity

Энэ V1 backend нь:

```text
LOW → MEDIUM complexity
```

гэж үзэж болно.

Хамгийн гол backend ажлууд:

```text
1. Form CRUD
2. Question builder CRUD
3. Option CRUD
4. PDF upload
5. Submission save
6. Answer validation
7. Result aggregation
```

Энд complex workflow байхгүй учраас architecture энгийн байна.

---

# 27. Implementation Order

Recommended implementation order:

```text
1. Database migrations
2. Models + relationships
3. Admin Form CRUD
4. Question builder API
5. Option management
6. PDF upload
7. Portal form detail API
8. Submission API
9. Admin result API
10. Graph / trend API
```

---

# 28. Final Backend Flow

## Admin

```text
Create Survey
    ↓
Add Questions
    ↓
Add Options
    ↓
Set Start / End Date
    ↓
Publish
```

## Portal

```text
Get Active Forms
    ↓
Open Survey / Poll
    ↓
Load Questions
    ↓
Fill Answers
    ↓
Submit
```

## Result

```text
Submissions
    ↓
Answers
    ↓
Aggregate
    ↓
Count / Percentage
    ↓
Admin Graph
```

---

# 29. Summary

V1-ийн хувьд backend-ийн үндсэн data model:

```text
Form
Question
Option
Submission
Answer
```

гэсэн 5 үндсэн ойлголт дээр төвлөрнө.

Poll дээр нэмэлтээр:

```text
Document / PDF
```

холбогдоно.

Энэ бүтэц нь одоогийн mockup-ийг real project болгоход хангалттай бөгөөд шаардлагагүй complex functionality оруулахгүй.
