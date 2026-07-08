import json

import conversation_store as cs


def test_start_append_and_get_conversation(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))

    session_id = cs.start_conversation(user_id="user-1", metadata={"client": "test"})
    assert session_id

    turn_id = cs.append_turn(
        session_id=session_id,
        prompt="hi",
        response="hello",
        rating=1,
        skill="sift-stylus-research",
        metadata={"latency_ms": 5},
    )
    cs.append_turn(session_id=session_id, prompt="again", response="hello 2")

    thread = cs.get_conversation(session_id)
    assert thread["session_id"] == session_id
    assert thread["user_id"] == "user-1"
    assert len(thread["turns"]) == 2
    assert thread["turns"][0]["turn_id"] == turn_id
    assert thread["turns"][0]["rating"] == 1
    assert thread["turns"][0]["skill"] == "sift-stylus-research"


def test_get_conversation_unknown_session_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    assert cs.get_conversation("nope") == {}


def test_append_turn_rejects_bad_rating(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    try:
        cs.append_turn(session_id="s", prompt="p", response="r", rating=2)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_export_conversations_filters_and_sorts(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    # export reads feedback_events.jsonl (rated outputs)
    path = tmp_path / "feedback_events.jsonl"
    rows = [
        {"id": "b", "prompt": "p2", "response": "r2", "rating": 1, "skill": "s", "timestamp": 200},
        {"id": "a", "prompt": "p1", "response": "r1", "rating": 1, "skill": "s", "timestamp": 100},
        {"id": "c", "prompt": "p3", "response": "r3", "rating": -1, "skill": "s", "timestamp": 300},
        {"id": "d", "prompt": "p4", "response": "r4", "timestamp": 400},  # no rating -> skipped
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

    exported = cs.export_conversations(min_rating=1, max_turns=10)
    assert [t["turn_id"] for t in exported] == ["a", "b"]  # rating>=1, sorted by ts

    truncated = cs.export_conversations(min_rating=1, max_turns=1)
    assert len(truncated) == 1 and truncated[0]["turn_id"] == "a"


def test_export_conversations_validates_args(monkeypatch, tmp_path):
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    for kwargs in ({"min_rating": 5}, {"max_turns": 0}):
        try:
            cs.export_conversations(**kwargs)
            assert False, f"expected ValueError for {kwargs}"
        except ValueError:
            pass
