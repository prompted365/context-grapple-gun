"""The delegation order ruled at /review 821 Q2, kept as a permanent test over the three seat specs
(ruled /review 825 H4: the verifier at review-824-evidence/build-delegation-order-three-specs/
verify_delegation_order.py becomes a test, so a later edit that moves the task off the last block goes red).

The ruled order, quoted from the ruling receipt: "what the work is NOT first, its purpose second to last,
the thing itself last". Two assertions per spec, over the BODY (frontmatter excluded — the harness parses
frontmatter; the ruling is about the delegating text):

  A. opens_with_is_not          — the first non-empty body line starts with "WHAT THIS WORK IS NOT"
  B. ends_with_serves_then_task — the LAST non-empty paragraph starts with "THE TASK, last:" AND the
                                  paragraph immediately before it starts with "WHAT THIS SERVES:"

Baseline at landing (tic 826): 6 of 6 on the live specs; 0 of 6 on the pre-reorder bytes (the tic-824
build's REVERT-CONTROL.log). The three specs are named here by file, not discovered by glob, so a
fourth seat spec is not silently held to this order until a ruling says so.
"""
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
SPECS = ["harpoon-build-citizen.md", "harpoon-drain-citizen.md", "cpr-stepper.md"]


def body_of(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return lines
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[i + 1:]
    return lines


def paragraphs(body_lines):
    paras, cur = [], []
    for ln in body_lines:
        if ln.strip() == "":
            if cur:
                paras.append("\n".join(cur))
                cur = []
        else:
            cur.append(ln)
    if cur:
        paras.append("\n".join(cur))
    return paras


def _paras(name):
    path = AGENTS_DIR / name
    assert path.is_file(), f"seat spec missing at {path}"
    paras = paragraphs(body_of(path.read_text()))
    assert paras, f"empty body: {path}"
    return paras


@pytest.mark.parametrize("name", SPECS)
def test_opens_with_is_not(name):
    first_line = _paras(name)[0].split("\n")[0]
    assert first_line.startswith("WHAT THIS WORK IS NOT"), (name, first_line[:96])


@pytest.mark.parametrize("name", SPECS)
def test_ends_with_serves_then_task(name):
    paras = _paras(name)
    last_head = paras[-1].split("\n")[0]
    prev_head = paras[-2].split("\n")[0] if len(paras) >= 2 else ""
    assert last_head.startswith("THE TASK, last:"), (name, last_head[:96])
    assert prev_head.startswith("WHAT THIS SERVES:"), (name, prev_head[:96])
