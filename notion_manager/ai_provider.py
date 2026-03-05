from __future__ import annotations

import time
from typing import Any

import anthropic


class AIProvider:
    """Wrapper around Anthropic Claude for structured Notion automation tasks."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-opus-4-5",
        max_tokens: int = 1024,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _complete(self, prompt: str) -> str:
        """Send a single-turn prompt to Claude and return the text response."""
        delay = 1.0
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                message = self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                return message.content[0].text
            except anthropic.APIError as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    time.sleep(delay)
                    delay *= self._backoff_factor
        raise last_exc  # type: ignore[misc]

    def _complete_structured(self, prompt: str, fallback: Any = None) -> Any:
        """Send a prompt expecting JSON and return the parsed result."""
        import json
        raw = self._complete(prompt).strip()
        # Try to extract JSON object or array
        for open_ch, close_ch in [("{", "}"), ("[", "]")]:
            try:
                start = raw.index(open_ch)
                end = raw.rindex(close_ch) + 1
                return json.loads(raw[start:end])
            except (ValueError, json.JSONDecodeError):
                continue
        return fallback if fallback is not None else {"raw": raw}

    # ------------------------------------------------------------------
    # Public task methods
    # ------------------------------------------------------------------

    def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Return a concise summary of text in at most max_sentences sentences."""
        prompt = (
            f"Summarize the following text in at most {max_sentences} sentences. "
            "Return only the summary, no preamble.\n\n"
            f"{text}"
        )
        return self._complete(prompt).strip()

    def classify_tags(self, text: str, available_tags: list[str] | None = None) -> list[str]:
        """Return a list of relevant tags for the given text."""
        if available_tags:
            tag_hint = "Choose only from these tags: " + ", ".join(available_tags) + "."
        else:
            tag_hint = "Invent concise, lowercase, hyphenated tags."
        prompt = (
            f"Classify the following text with relevant tags. {tag_hint}\n"
            "Return a JSON array of tag strings only, no explanation.\n\n"
            f"{text}"
        )
        raw = self._complete(prompt).strip()
        # Best-effort parse: extract list from response
        import json
        try:
            start = raw.index("[")
            end = raw.rindex("]") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]

    def answer_question(self, question: str, context: str) -> str:
        """Answer question using the provided context."""
        prompt = (
            "Use only the context below to answer the question. "
            "If the answer is not in the context, say 'I don't know.'\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )
        return self._complete(prompt).strip()

    def analyze_tasks(self, tasks_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze a tasks dict and return structured insights."""
        import json
        prompt = (
            "Analyze the following tasks data and return a JSON object with keys: "
            "'summary' (string), 'priorities' (list of strings), "
            "'blockers' (list of strings), 'next_actions' (list of strings).\n"
            "Return only valid JSON.\n\n"
            f"{json.dumps(tasks_data, ensure_ascii=False, indent=2)}"
        )
        raw = self._complete(prompt).strip()
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return {"raw": raw}

    def summarize_meeting(self, text: str) -> dict:
        """Extract decisions, action items, attendees from meeting notes."""
        prompt = (
            "Analyze these meeting notes and extract:\n"
            "1. Key decisions made\n"
            "2. Action items (with assignees if mentioned)\n"
            "3. Attendees mentioned\n"
            "4. Brief summary (2-3 sentences)\n\n"
            "Return as JSON: {\"decisions\": [...], \"action_items\": [...], \"attendees\": [...], \"summary\": \"...\"}\n\n"
            f"Meeting notes:\n{text}"
        )
        response = self._complete(prompt)
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return {"decisions": [], "action_items": [], "attendees": [], "summary": response}

    def generate_digest(self, changes_text: str) -> str:
        """Generate a digest summary of recent changes."""
        prompt = (
            "다음은 최근 변경된 노션 페이지 목록입니다. 변경사항을 간결하게 요약하는 다이제스트를 작성해주세요.\n\n"
            f"{changes_text}"
        )
        return self._complete(prompt)

    def extract_reading_notes(self, text: str) -> dict:
        """Extract key insights, concepts, and quotes from reading notes."""
        prompt = (
            "Analyze these reading notes and extract:\n"
            "1. Key insights (main takeaways)\n"
            "2. Main concepts discussed\n"
            "3. Notable quotes\n"
            "4. Brief summary\n\n"
            "Return as JSON: {\"key_insights\": [...], \"main_concepts\": [...], \"quotes\": [...], \"summary\": \"...\"}\n\n"
            f"Reading notes:\n{text}"
        )
        response = self._complete(prompt)
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return {"key_insights": [], "main_concepts": [], "quotes": [], "summary": response}

    def convert_to_bullets(self, text: str) -> list[str]:
        """Convert long-form text to structured bullet points."""
        prompt = (
            "다음 텍스트를 구조화된 bullet point 목록으로 변환해주세요. "
            "각 bullet point는 한 줄로, 핵심 내용만 포함해주세요.\n"
            "Return as JSON array of strings: [\"point 1\", \"point 2\", ...]\n\n"
            f"{text}"
        )
        response = self._complete(prompt)
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return [line.strip("- •").strip() for line in response.strip().split("\n") if line.strip()]

    def expand_content(self, text: str, style: str = "formal") -> str:
        """Expand short notes into structured document."""
        style_desc = "격식체로 전문적인" if style == "formal" else "친근하고 캐주얼한"
        prompt = (
            f"다음 짧은 메모를 {style_desc} 톤으로 구조화된 문서로 확장해주세요.\n"
            "섹션 제목, 설명, 세부사항을 포함해주세요.\n\n"
            f"메모:\n{text}"
        )
        return self._complete(prompt)

    def translate(self, text: str, target_lang: str = "en") -> str:
        """Translate text to the target language."""
        prompt = f"Translate the following text to {target_lang}. Return only the translated text.\n\n{text}"
        return self._complete(prompt)

    def analyze_sentiment(self, text: str) -> dict:
        """Analyze emotional tone of text."""
        prompt = (
            "Analyze the emotional tone of this text.\n"
            "Return as JSON: {\"sentiment\": \"positive\"|\"negative\"|\"neutral\"|\"mixed\", "
            "\"score\": float (-1.0 to 1.0), \"keywords\": [\"emotion words\"]}\n\n"
            f"Text:\n{text[:3000]}"
        )
        response = self._complete(prompt)
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return {"sentiment": "neutral", "score": 0.0, "keywords": []}

    def analyze_goals(self, goals_data: str) -> str:
        """Generate insights about goal achievement."""
        prompt = (
            "다음 목표 달성 현황을 분석하고 인사이트를 제공해주세요.\n"
            "잘 진행되는 부분, 개선이 필요한 부분, 제안사항을 포함해주세요.\n\n"
            f"{goals_data}"
        )
        return self._complete(prompt)

    def generate_faq(self, text: str) -> list[dict]:
        """Generate FAQ from document content."""
        prompt = (
            "다음 문서 내용을 바탕으로 자주 묻는 질문(FAQ) 5-10개를 생성해주세요.\n"
            "Return as JSON array: [{\"question\": \"...\", \"answer\": \"...\"}]\n\n"
            f"Document:\n{text[:4000]}"
        )
        response = self._complete(prompt)
        try:
            import json
            return json.loads(response)
        except (json.JSONDecodeError, ValueError):
            return [{"question": "Error parsing FAQ", "answer": response}]

    def generate_release_notes(self, changes_text: str, version: str = "") -> str:
        """Generate release notes from changelog entries."""
        ver_str = f" (Version {version})" if version else ""
        prompt = (
            f"다음 변경 로그를 바탕으로 릴리즈 노트{ver_str}를 작성해주세요.\n"
            "카테고리별로 정리해주세요: 새 기능, 개선사항, 버그 수정, 기타.\n\n"
            f"{changes_text}"
        )
        return self._complete(prompt)

    def generate_weekly_review(self, activity_text: str) -> str:
        """Generate weekly review from activity data."""
        prompt = (
            "다음 활동 데이터를 바탕으로 주간 리뷰를 작성해주세요.\n"
            "이번 주 성과, 배운 점, 다음 주 계획을 포함해주세요.\n\n"
            f"{activity_text}"
        )
        return self._complete(prompt)
