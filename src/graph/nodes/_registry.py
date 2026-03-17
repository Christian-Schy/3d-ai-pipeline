"""Agent registry — replaces 12 individual lazy-init _get_*() functions."""
from functools import lru_cache


@lru_cache(maxsize=None)
def get_agent(agent_class):
    """Return a singleton instance of the given agent class."""
    return agent_class()
