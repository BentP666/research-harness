"""Paper + topic fixtures for offline E2E.

- topics/*.json:    topic brief (name, venue, deadline, direction, seeds)
- papers/*.json:    paper metadata (arxiv_id, title, abstract, authors, venue, year)
- loader.py:        load_topic(db, spec_name) → LoadedTopic

Available topics:
- small_tfr              (smoke, 5 papers, terminal at build)
- loopback_evidence      (pre_merge, 5 papers, forces analyze→build loopback)
- full_chain_benchmark   (nightly, 5 papers, reaches write via stub experiment)
"""

from .loader import LoadedTopic, list_topic_specs, load_topic

__all__ = ["LoadedTopic", "list_topic_specs", "load_topic"]
