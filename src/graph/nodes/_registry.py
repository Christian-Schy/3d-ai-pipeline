"""Agent registry — replaces 12 individual lazy-init _get_*() functions."""
from functools import lru_cache


@lru_cache(maxsize=None)
def get_agent(agent_class):
    """Return a singleton instance of the given agent class."""
    return agent_class()


def get_raw_response(agent_class) -> str | None:
    """Get the last raw LLM response from a cached agent instance."""
    agent = get_agent(agent_class)
    return getattr(agent, "_last_raw_response", None)
