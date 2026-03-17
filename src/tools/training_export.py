"""
src/tools/training_export.py — Offline tool for extracting training data from session logs.

Provides functions to extract SFT and DPO training pairs from runs.jsonl.
Not integrated into the pipeline — used post-hoc when enough data is collected.

Usage:
    from src.tools.session_logger import load_sessions
    from src.tools.training_export import extract_training_pairs, build_dpo_pairs

    sessions = load_sessions()

    # SFT: good planner outputs
    sft_pairs = extract_training_pairs(sessions, "planner",
                    only_successful=True, exclude_revisions=True)

    # DPO: paired good/bad planner outputs for the same user_input
    dpo_pairs = build_dpo_pairs(sessions, "planner")
"""


def extract_training_pairs(
    sessions: list[dict],
    agent_name: str,
    only_successful: bool = True,
    exclude_revisions: bool = True,
) -> list[dict]:
    """Extract input/output pairs for a specific agent from session logs.

    Args:
        sessions:          List of session dicts (from load_sessions()).
        agent_name:        Which agent to extract: "interpreter", "planner", "coder", etc.
        only_successful:   If True, only sessions where feedback="good".
                           If False, only sessions where feedback="bad".
        exclude_revisions: If True, skip traces where revision=True.

    Returns:
        List of dicts with: user_input, agent_input, agent_output, feedback,
        error_agent, error_note, run_id.
    """
    pairs = []
    for session in sessions:
        if only_successful and session.get("feedback") != "good":
            continue
        if not only_successful and session.get("feedback") != "bad":
            continue

        for trace in session.get("agent_traces", []):
            if trace.get("agent") != agent_name:
                continue
            if exclude_revisions and trace.get("revision", False):
                continue

            pairs.append({
                "user_input": session.get("user_input", ""),
                "agent_input": trace.get("input"),
                "agent_output": trace.get("output"),
                "feedback": session.get("feedback", "good"),
                "error_agent": session.get("error_agent"),
                "error_note": session.get("error_note"),
                "run_id": session.get("run_id", ""),
            })

    return pairs


def build_dpo_pairs(
    sessions: list[dict],
    agent_name: str,
) -> list[dict]:
    """Build DPO pairs: same user_input, one good output, one bad output.

    Works best when the same tasks have been run multiple times (batch testing).

    Args:
        sessions:   List of session dicts (from load_sessions()).
        agent_name: Which agent to pair: "interpreter", "planner", "coder", etc.

    Returns:
        List of dicts with: user_input, chosen (good output), rejected (bad output),
        error_note.
    """
    good = extract_training_pairs(sessions, agent_name,
                                  only_successful=True, exclude_revisions=True)
    bad = extract_training_pairs(sessions, agent_name,
                                 only_successful=False, exclude_revisions=True)

    good_by_input: dict[str, list] = {}
    for g in good:
        key = g["user_input"].strip().lower()
        good_by_input.setdefault(key, []).append(g)

    pairs = []
    for b in bad:
        key = b["user_input"].strip().lower()
        if key in good_by_input and good_by_input[key]:
            pairs.append({
                "user_input": b["user_input"],
                "chosen": good_by_input[key][0]["agent_output"],
                "rejected": b["agent_output"],
                "error_note": b.get("error_note", ""),
            })

    return pairs
