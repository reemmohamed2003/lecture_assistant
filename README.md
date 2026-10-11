# Rafeeq - M4: learner profile, quizzes and paper-quiz grader

M4 is the part of Rafeeq that knows **what each student is weak at** and **tests them on it**.
It does three things:

1. **Learner profile**: mastery per topic, updated from events sent by the other modules.
2. **Quiz agent**: an LLM writes multiple-choice questions from the course material, aiming at the student's weak topics.
3. **Paper-quiz grader**: print the quiz as a PDF, solve it on paper, photograph the answer sheet, and the grader reads the filled bubbles with OpenCV.

Stack: FastAPI, Pydantic v2, SQLAlchemy 2 (SQLite), PyMuPDF, OpenCV, NumPy, pytest, uv, Python 3.11.

---

## 1. Setup

```powershell
cd D:\m4
uv sync
```

Create a `.env` file in `D:\m4` (never commit it, never share keys):

```
# LLM that writes the questions
M4_LLM_PROVIDER=compat
M4_LLM_MODEL=qwen/qwen3.8-27b
COMPAT_BASE_URL=https://api.groq.com/openai/v1
COMPAT_API_KEY=your_key_here

# optional: a second model that solves each question blind and drops unclear ones
M4_VERIFY_PROVIDER=compat
M4_VERIFY_MODEL=openai/gpt-oss-120b

# optional
M4_DATABASE_URL=sqlite:///m4_dev.db
M4_SHEETS_DIR=data/sheets_out
```

Providers (`M4_LLM_PROVIDER`):

| Provider | What it is | Needed |
|---|---|---|
| `gemini` (default) | Google Gemini, default model `gemini-3.5-flash-lite` | Gemini key in `.env` |
| `openai` | OpenAI, default model `gpt-4o-mini` | OpenAI key in `.env` |
| `compat` | Any OpenAI-compatible host, for example Groq (free tier) | `COMPAT_BASE_URL`, `COMPAT_API_KEY`, `M4_LLM_MODEL` |

To go back to Gemini: set `M4_LLM_PROVIDER=gemini` and comment out `M4_LLM_MODEL` with `#`.
**Restart the server after any `.env` change.**

Rate limits are handled: a 503 is retried (2 s, doubling), a 429 waits at least 20 s, and `insufficient_quota` is not retried.

---

## 2. Run

```powershell
cd D:\m4
uv run uvicorn m4.main:app --reload
```

Wait for `Application startup complete`, then open the interactive docs:

```
http://127.0.0.1:8000/docs
```

(no dot or slash after `docs`).

Stop the server with `Ctrl+C`. The quizzes are kept in `m4_dev.db` and the PDFs in `data\sheets_out`, so they survive a restart.

---

## 3. API (the M4 contract)

| Method and path | What it does |
|---|---|
| `POST /internal/record_event` | Other modules report what the student did. `kind` is `question`, `quiz`, `handwriting` or `attendance`. |
| `GET /rooms/{id}/me/profile` | Mastery per topic and the weak topics of the current student. |
| `GET /rooms/{id}/topics` | The topics of the course (used to pick a topic for a quiz). |
| `POST /rooms/{id}/quizzes` | Create a quiz. Body: `{"n": 5, "mode": "screen" or "paper", "topic_id": "optional"}` |
| `POST /quizzes/{id}/submit` | Submit answers typed on screen. A quiz can be submitted **once** (a second try returns 409). |
| `GET /quizzes/{id}/sheet.pdf` | Download the printable PDF of a paper quiz. |
| `POST /quizzes/{id}/grade-sheet` | Upload a photo or screenshot of the filled answer sheet and get the detected answers. |
| `GET /rooms/{id}/class-profile` | Teacher view: mastery across the class. |
| `GET /rooms/{id}/wrong-answers` | The most missed questions. |

Common errors: `404` = wrong quiz id or topic id (do not leave the placeholder `string`), `409` = already submitted, `422` = the request body has the wrong shape, `503` = the LLM could not produce enough valid questions (try again).

---

## 4. Mastery rules

- Start at 0.5 for every topic.
- After a quiz on a topic: `new = 0.7 * old + 0.3 * score`.
- **Weak topic** = mastery below 0.6 after at least 2 attempts, or 3 or more questions asked about it since the last quiz.
- `question` events do not move mastery. `attendance` events are ignored.

---

## 5. Quizzes

### 5.1 Create a quiz

In `/docs` open `POST /rooms/{room_id}/quizzes`, press **Try it out**, and send for example:

```json
{ "n": 5, "mode": "paper", "topic_id": "2-tokens-and-embeddings" }
```

- `mode: "screen"`: the student answers on screen and sends the answers to `/submit`.
- `mode: "paper"`: the reply has a `sheet_pdf` link; the PDF is also saved in `data\sheets_out\<quiz_id>.pdf`.
- `topic_id` is optional. Without it, about 60% of the questions come from the student's weak topics.

Save the `quiz_id` from the reply. Example topic ids for the demo book: `1-an-introduction-to-large-language-mode`, `2-tokens-and-embeddings`, `4-text-classification`, `7-advanced-text-generation-techniques-an`, `9-multimodal-large-language-models`, `10-creating-text-embedding-models`. Theory chapters give the best questions.

### 5.2 How a question is made and checked

1. A page of the book is chosen. Approved questions from M5 come first, then generated ones.
2. The LLM writes one question with four options and an explanation.
3. The **validator** rejects a question if it: is too short, points at "the text / passage / page / figure / this specific text", says "described in", "mentioned in", "referenced in", has an empty or duplicated option, has an option that repeats the question, has an empty explanation, or has no source page.
4. If rejected, it retries once and tells the model why.
5. If a verifier is set, a **second model answers the question using only the source page**. If it picks a different answer or says the page does not support it, the question is dropped.
6. The options are shuffled (LLMs love putting the answer in slot B). Topic, file and page always come from the page, never from the LLM.

What code cannot fix: a wrong fact inside an explanation, numeric trivia, and distractors that are too easy. **Read the questions before a demo** and keep the approved ones.

### 5.3 Quality check script

```powershell
uv run python -m m4.eval.judge_quiz --help
```

It generates questions and asks a separate judge model to solve them blind. Options: `--gen-provider`, `--gen-model`, `--judge-provider`, `--judge-model`, `--items-file`, `--report`, `--sleep`, `--reuse`. Note: it does **not** read `M4_LLM_PROVIDER`; use its own flags, otherwise it falls back to Gemini.

---

## 6. Paper quiz: print, solve, photograph, grade

### 6.1 Download the PDF

Either from `/docs`: `GET /quizzes/{quiz_id}/sheet.pdf` -> Try it out -> Execute -> **Download file**.
Or open the saved file:

```powershell
cd D:\m4
start data\sheets_out\quiz-62a6875b.pdf
```

Make a blank sheet for testing (no questions):

```powershell
uv run python -m m4.sheet.make_pdf --n 20 --quiz-id demo --out data\sheet_demo.pdf
```

### 6.2 The PDF

- **Page 1**: the answer sheet: header, name and score, rows of A B C D bubbles, and four black squares in the corners.
- **Page 2 onwards**: the questions with their options.

### 6.3 Print and solve

1. Print on A4 at **100%** ("Fit to page" off).
2. Solve from the question pages. For each question, fill **one** bubble completely on page 1 with a dark pen or pencil.
3. Photograph page 1 from above, in good light, with **all four black squares in the picture** and nothing cut off. No stray marks near the corners.

### 6.4 Grade

In `/docs` open `POST /quizzes/{quiz_id}/grade-sheet`, enter the quiz id, choose the image, press **Execute**. The reply:

```json
{
  "answers": [ { "item_id": "...", "choice": 0, "confidence": 1 } ],
  "score": 0.5,
  "needs_review": ["...-g4", "...-g5"]
}
```

- `choice`: 0 = A, 1 = B, 2 = C, 3 = D, or `null` when blank or marked twice.
- `confidence`: how clearly the bubble is filled (0 to 1).
- `needs_review`: questions left blank or marked twice. They count as not correct until a teacher reviews them.
- `score`: the fraction correct (0.5 means 5 of 10).

If the photo is not usable the reply is an error with a clear message, for example "the four corner squares do not form the page; photograph the WHOLE page ...". The grader refuses to guess when the four corner squares are not all visible.

### 6.5 How the grader works

1. Find the four black corner squares (26 pt squares at (40,40), (555,40), (40,802), (555,802)).
2. Check that they form the same rectangle as the printed page, otherwise reject.
3. Straighten the page with a perspective warp (2 px per point).
4. Remove shadows and uneven light.
5. Measure how dark each bubble is. A bubble counts as marked at 30% fill. If a second bubble in the same row is at least 60% as strong as the first, the row is "two marks".

Layout numbers (bubble radius 10, 15 rows per column, 2 columns, up to 30 questions per sheet) live in `m4/sheet/layout.py`. The PDF maker, the grader and the tests all read them, so change them in one place only.

Status: tested on 300 synthetic sheets (100% of marks read correctly) and on a clean screen capture of a filled sheet (all 7 filled rows read correctly, blank and double-marked rows flagged). **A real phone photo of a printed sheet is not tested yet.**

### 6.6 Score report PDF

Make a PDF report of the result (score, your answer, the correct answer, the explanation and the source page for every question).

1. Save the reply of the quiz creation as `quiz.json` and the reply of `grade-sheet` as `result.json` in `D:\m4` (plain JSON only: the file must start with `{` and end with `}`, no code-fence lines).
2. Run:

```powershell
cd D:\m4
uv run python -m m4.sheet.make_report quiz.json result.json --out data\report.pdf
start data\report.pdf
```

Green = correct, red = wrong, amber = needs review.

---

## 7. Tests

```powershell
uv run pytest
```

Expected: all tests pass (75 at the time of writing). Run it after every change.

---

## 8. Troubleshooting

| Problem | Cause and fix |
|---|---|
| `Error loading ASGI app. Could not import module` | Wrong module name. Use `m4.main:app`. |
| `404 Not Found` on `/docs.` | Remove the dot: `/docs`. |
| `404` on a quiz endpoint | Wrong or placeholder id (`string`), or a different `m4_dev.db`. |
| `500` when creating a quiz, log shows Gemini 404 | Provider and model do not match. Fix `.env` and restart. |
| `409` on submit | The quiz was already submitted. Create a new quiz. |
| `422` | The request body has the wrong shape. Copy the example shown in `/docs`. |
| `503` creating a quiz | The LLM rate limit or too many rejected questions. Wait and retry, or switch provider. |
| `grade-sheet` says the corner squares do not form the page | The image is cropped or has stray dark marks. Photograph or capture the whole page. |
| `FileNotFoundError` in `make_report` | The file name is wrong. Check with `dir *.json*`. |
| Saved `quiz.json` is actually `quiz.json.txt` | In Notepad choose **Save as type: All files**, or use VS Code. |

---

## 9. Project layout

```
m4/
  api.py            the 9 routes
  contracts.py      request and response models
  deps.py           LLM, verifier, chunks and approved-items providers
  profile/          events, mastery, weak-topic rules
  quiz/
    llm.py          gemini, openai, compat providers
    generator.py    prompt, retry, shuffle, blind verifier
    validator.py    rules a question must pass
    service.py      create quiz, submit, save
  sheet/
    layout.py       positions on the answer sheet
    make_pdf.py     printable PDF
    grader.py       OpenCV reader
    make_report.py  score report PDF
    synthetic.py    fake photos for tests
  eval/judge_quiz.py  blind-judge quality check
  dev/              the demo book reader (stand-in for M2 retrieval)
  tests/
```

---

## 10. Integration with the team

- **M1** (users and rooms): replaces the stand-in `current_user_id`.
- **M2** (retrieval): provides `get_chunks(room_id, topic_id)` returning `{text, topic_id, topic_name, file, page}`. Until then M4 reads the book through `dev/book_chunks.py`.
- **M5** (approved questions): provides approved items; the stand-in returns an empty list.
- Work stays on branch `m4-quiz-profile`; open the PR only when M4 is done.

---

## 11. Known limits

- Questions are multiple choice only, in English (the source book is English).
- The paper grader is verified on synthetic sheets and a clean screen capture, not yet on real phone photos.
- A quiz can be submitted once.
- Generated questions still need a human read before a demo.