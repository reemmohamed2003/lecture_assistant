"""Dependencies the API needs. Stand-ins for other members' work are marked TODO."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def current_user_id() -> str:
    # TODO: use M1's current_user() / require_member(room_id)
    return "demo-student"


@lru_cache
def _llm():
    from m4.quiz.llm import make_llm

    return make_llm(os.getenv("M4_LLM_PROVIDER", "gemini"), os.getenv("M4_LLM_MODEL") or None)


def get_llm():
    return _llm()


@lru_cache
def _chunks() -> list[dict]:
    # TODO: replace with M2's retrieve(room_id, ...) when it is live
    from m4.dev.book_chunks import load_chunks

    return load_chunks(os.getenv("M4_BOOK_PDF", "data/Hands-On_Large_Language_Models.pdf"))


def get_chunks() -> list[dict]:
    return _chunks()


def get_approved_items():
    # TODO: call M5's approved-items endpoint. Empty for now, so quizzes fall
    # back to generated items without an error.
    return lambda room_id, topic_ids: []