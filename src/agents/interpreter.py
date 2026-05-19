"""
src/agents/interpreter.py — Dialog agent that refines vague requests into specs.

The Interpreter is the first agent the user talks to.
It has two jobs:

  1. Decide if the request already contains enough information.
     "A 30mm cube" → complete immediately, no questions needed.
     "A box" → missing dimensions, ask.

  2. If incomplete: generate one focused clarifying question.
     Ask one thing at a time — not a list of 5 questions at once.

When is_complete=True, the Interpreter writes a clean specification
string that the Planner can work with directly.

The graph pauses here when a question needs to be asked (interrupt()).
The caller (main.py / app.py) handles showing the question and resuming.

Model: qwen3:8b — dialog doesn't need the big model, speed matters here.
"""

import structlog

from src.agents.base import BaseAgent
from src.graph.state import PipelineState
from src.rag.interpreter_rag import InterpreterRAG
from src.utils.prompt_loader import load_prompt

log = structlog.get_logger()

_prompt = load_prompt("prompt_interpreter.py")
SYSTEM_PROMPT = _prompt.SYSTEM_PROMPT


class InterpreterAgent(BaseAgent):
    """Conducts a clarifying dialog until the specification is complete.

    Called by interpreter_node. If a question needs to be asked,
    the node uses LangGraph's interrupt() to pause the graph.
    The caller resumes with the user's answer.
    """

    name = "interpreter"

    @property
    def model(self) -> str:
        from src.config.loader import get_config
        return get_config().models.interpreter

    def __init__(self):
        super().__init__()
        self._rag = InterpreterRAG()
        self._rag_ready = False

    def _ensure_rag(self):
        """Build RAG on first use — not at import/instantiation time."""
        if not self._rag_ready:
            try:
                self._rag.build()
            except FileNotFoundError:
                self.log.warning("interpreter_rag_knowledge_missing",
                                 path="data/knowledge/interpreter")
            self._rag_ready = True

    def process(self, state: PipelineState) -> dict:
        """Evaluate the current dialog state and return next action.

        Returns a dict with:
          is_complete: bool
          question: str    — empty if complete
          specification: str — empty if not yet complete
        """
        description = state.get("description", "")
        # If Visioner already extracted a partial spec, use it as starting point
        visioner_spec = state.get("specification", "")
        if visioner_spec and not description:
            description = f"[From image analysis]: {visioner_spec}"
        messages = state.get("messages", [])

        # Build a conversation summary for the LLM
        # messages is a list of LangChain message objects (from add_messages)
        history = self._format_history(messages)

        prompt = self._build_prompt(description, history)

        # Enrich with RAG examples of good specs and useful questions
        self._ensure_rag()
        prompt = self._rag.enrich_prompt(prompt, description)

        try:
            result = self.call_json(prompt, system=SYSTEM_PROMPT)
            is_complete = bool(result.get("is_complete", False))
            question = (result.get("question") or "").strip()
            specification = (result.get("specification") or "").strip()

            self.log.info("interpreter_response",
                          is_complete=is_complete,
                          has_question=bool(question),
                          spec_len=len(specification))

            # Log content for the UI chat display
            if is_complete and specification:
                self.log.info("interpreter_spec_done", spec=specification[:400])
            elif question:
                self.log.info("interpreter_question_text", question=question[:300])

            features_found = result.get("features_found", [])
            if not isinstance(features_found, list):
                features_found = []

            return {
                "is_complete": is_complete,
                "question": question,
                "specification": specification,
                "interpreter_features": features_found,
            }

        except (ValueError, ConnectionRefusedError) as e:
            # Fallback: treat the description as complete to keep pipeline moving
            self.log.error("interpreter_failed", error=str(e))
            return {
                "is_complete": True,
                "question": "",
                "specification": description,
                "interpreter_features": [],
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_prompt(self, description: str, history: str) -> str:
        """Build the prompt from the original description + dialog history."""
        if history:
            return (
                f"Original request: {description}\n\n"
                f"Dialog so far:\n{history}\n\n"
                "The user has answered the previous question. "
                "Based on all the information above, is the specification now complete? "
                "Do NOT repeat a question that was already answered. "
                "If you have enough info to build the model, mark it complete."
            )
        return (
            f"User request: {description}\n\n"
            "Is this request complete enough to build a 3D model? "
            "Only ask if a critical dimension is truly missing."
        )

    def _format_history(self, messages: list) -> str:
        """Convert LangChain message objects to a readable string.

        messages come from the 'messages' field in PipelineState,
        which uses add_messages — so they are HumanMessage / AIMessage objects.
        """
        if not messages:
            return ""

        lines = []
        for msg in messages:
            # LangChain messages have a 'type' attribute: 'human' or 'ai'
            role = getattr(msg, "type", "unknown")
            content = getattr(msg, "content", str(msg))
            prefix = "User" if role == "human" else "Assistant"
            lines.append(f"{prefix}: {content}")

        return "\n".join(lines)