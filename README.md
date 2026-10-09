# Rafeeq M4: Learner Profile, Quizzes and Paper Grader

M4 is the part of Rafeeq (رفيق), the Arabic/English multi-agent learning
copilot, that tracks what each student knows, writes quizzes from the course
book, and grades paper quizzes from a phone photo.

| Part | What it does | Type |
|---|---|---|
| Quiz agent | Writes multiple-choice questions from book pages, validates them, saves the quiz | LLM agent |
| Paper grader | Prints a quiz as a bubble sheet, reads a photo of it, grades it | Computer vision (OpenCV) |
| Learner profile | Tracks mastery per student per topic and flags weak topics | Rules |
| Instructor data | Class-level weak topics and most-missed questions, with no student names | Rules |
| Quality judge | Offline check of question quality (not part of the API) | LLM judge |

## Project layout

```
m4/
  contracts.py        shared Pydantic schemas (add fields freely; renaming needs a yes from every consumer)
  api.py              the M4 router, 9 routes (M1 mounts it)
  deps.py             session, chunks, LLM, and stand-ins for other members' work
  stubs.py            sample JSON for every endpoint
  main.py             runs M4 alone for local development
  profile/            mastery.py, service.py, models.py, db.py
  quiz/               generator.py, validator.py, llm.py, service.py, models.py
  sheet/              layout.py, make_pdf.py, grader.py, synthetic.py
  eval/               judge_quiz.py, grade_sheets.py
  dev/book_chunks.py  loads the book PDF into chunks (temporary, until M2's retrieval is live)
  tests/              70 tests
```

## Setup

Requires Python 3.11 and [uv](https://docs.astral.sh/uv/).

```powershell
uv sync
```

Create a `.env` file (it is in `.gitignore`; never commit keys):

```
M4_LLM_PROVIDER=gemini
GEMINI_API_KEY=your-key
```

### LLM provider

| Variable | Meaning |
|---|---|
| `M4_LLM_PROVIDER` | `gemini` (default), `openai`, or `compat` |
| `M4_LLM_MODEL` | Model name. Leave empty to use the provider default |
| `GEMINI_API_KEY` | Needed for `gemini` (default model `gemini-3.5-flash-lite`) |
| `OPENAI_API_KEY` | Needed for `openai` (default model `gpt-4o-mini`) |
| `COMPAT_API_KEY` | Needed for `compat` |
| `COMPAT_BASE_URL` | Needed for `compat`, for example `https://api.groq.com/openai/v1` |
| `M4_BOOK_PDF` | Book used for questions (default `data/Hands-On_Large_Language_Models.pdf`) |
| `M4_DATABASE_URL` | Database URL. Default is a local SQLite file `m4_dev.db` |
| `M4_SHEETS_DIR` | Folder where generated answer sheets are stored |

`compat` works with any host that has an OpenAI-compatible API (Groq,
Cerebras, OpenRouter). Example with Groq and Qwen:

```
M4_LLM_PROVIDER=compat
M4_LLM_MODEL=qwen/qwen3.8-27b
COMPAT_BASE_URL=https://api.groq.com/openai/v1
COMPAT_API_KEY=your-key
```

Reasoning models print `<think>...</think>` first; M4 removes it before
reading the answer. Temporary errors are retried: 503 waits with a doubling
delay starting at 2 s, 429 waits at least 20 s, and billing errors
(`insufficient_quota`) are not retried.

## Run

```powershell
uv run uvicorn m4.main:app --reload
```

Open http://127.0.0.1:8000/docs to try the endpoints. Restart the server
after changing `.env`.

## API (9 routes)

| Route | Purpose |
|---|---|
| `POST /internal/record_event` | Record an event for a student (called by other members' services) |
| `GET /rooms/{id}/me/profile` | The current student's mastery per topic |
| `GET /rooms/{id}/topics` | Topics of the course |
| `POST /rooms/{id}/quizzes` | Create a quiz: `{n, mode: screen or paper, topic_id?}` |
| `POST /quizzes/{id}/submit` | Submit answers and get graded |
| `GET /quizzes/{id}/sheet.pdf` | Printable answer sheet and questions (paper mode) |
| `POST /quizzes/{id}/grade-sheet` | Upload a photo of the filled sheet and grade it |
| `GET /rooms/{id}/class-profile` | Instructor: class mastery per topic |
| `GET /rooms/{id}/wrong-answers` | Instructor: most-missed questions, students shown as hashed `s-xxxx` refs |

`record_event(user_id, room_id, topic_id, kind, score, meta)` where `kind` is
`question`, `quiz`, `handwriting` or `attendance`.

## How it works

### Mastery (profile/mastery.py)

- Starts at 0.5. On a `quiz` or `handwriting` event: `new = 0.7 * old + 0.3 * score`.
- `question` events do not change mastery; `attendance` is ignored.
- A topic is **weak** when mastery is below 0.6 after at least 2 attempts.
- A topic is also weak when the student asked 3 or more questions about it without taking a quiz.

### Quiz agent (quiz/)

- The LLM is injected as `llm(prompt) -> str`, so any provider works and tests use a fake.
- About 60% of the chunks come from the student's weak topics. Approved items from M5 come first.
- The validator rejects: stem shorter than 10 characters, phrases that need context ("according to the text"), empty or duplicate options, no explanation, no source page. A rejected item is retried once with the reasons.
- Options are shuffled. Topic, file and page always come from the chunk, never from the LLM.

### Paper grader (sheet/)

1. Find the 4 black corner squares and straighten the page.
2. Remove shadows (divide by an estimate of the empty paper).
3. Measure the ink inside each bubble.
4. Decide per question: blank, one mark, two marks, or unsure. Blank, double and low-confidence answers are flagged for review.

The sheet is A4 with up to 30 questions, 4 choices each. All positions live in `sheet/layout.py`, which the PDF maker and the grader both read.

Make a demo sheet:

```powershell
uv run python -m m4.sheet.make_pdf --n 20 --out data/sheet_demo.pdf
```

## Evaluation

### Question quality (offline judge)

A judge model sees each question and its source page without the answer key,
then we compare its answer with ours and ask if the page supports it. The
judge script does not read `M4_LLM_PROVIDER`; choose models with flags. Use a
judge from a different model family than the generator.

```powershell
uv run python -m m4.eval.judge_quiz --gen-provider compat --gen-model qwen/qwen3.8-27b `
    --judge-provider compat --judge-model openai/gpt-oss-120b `
    --items-file data/judge_items_qwen.json --report data/judge_report_qwen.json --sleep 5
```

Use `--reuse` to judge saved questions again, and a larger `--sleep` if you hit rate limits.

| Generator | Judge | Questions | First-try validation | Judge agrees | Page supports |
|---|---|---|---|---|---|
| Gemini 3.5 flash-lite | gpt-oss-120b | 20 | 95% | 100% | 100% |
| Qwen 3.8 27B | gpt-oss-120b | 20 | 95% | 100% | 100% |

Small sample judged by a model, not by humans. It is not ground truth, and a
manual review of a sample is still needed.

### Paper grader accuracy

100% on 300 synthetic sheets (fake sheets with simulated phone photos).
**Not yet tested on real printed and photographed sheets.** To measure real
accuracy, put photos in `data/sheets/` and write what you marked in
`data/sheets/truth.json`:

```json
{"sheet1.jpg": [0, 2, 1, null, 3]}
```

(0 to 3 = A to D, `null` = left blank), then:

```powershell
uv run python -m m4.eval.grade_sheets --dir data/sheets --truth data/sheets/truth.json
```

## Tests

```powershell
uv run pytest
```

70 tests, all use a fake LLM and need no network or keys.

## Integration status

| With | Status |
|---|---|
| M1 (auth and rooms) | Stand-in `current_user_id()` returns a demo user. Replace with M1's current user and role checks |
| M2 (knowledge base) | `get_chunks()` reads the book directly. Replace with M2's retrieval. Needed shape: `{text, topic_id, topic_name, file, page}` |
| M5 (question bank) | `get_approved_items()` returns an empty list. Replace with M5's approved-items endpoint |

## Known limits

- The paper grader needs good light and all four corners visible in the photo.
- Maximum 30 questions per sheet, 4 choices each.
- Free-tier LLM limits apply. Keep a second provider configured in `.env` and switch with one line.