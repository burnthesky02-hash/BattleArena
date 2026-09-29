"""Verifies the live-streaming "what's the model thinking" pipeline end to end
against a fake Ollama server that actually streams its response in small
chunks (simulating real token-by-token generation), rather than a mock that
mimics the earlier non-streaming API test elsewhere.

Checks:
  - The request Ollama receives actually asks for streaming (no format="json",
    which would rule out the free-text THINKING prefix), and carries the
    speed-tuning options (num_predict, keep_alive) from config.
  - Several "thinking_chunk" on_decision events fire as content streams in
    (proving live incremental display works, not just a final callback).
  - The live text shown to a UI never flashes partial "THINKING:"/"ACTION_JSON:"
    marker fragments and never shrinks -- it grows monotonically to exactly the
    model's intended sentence.
  - No JSON ever leaks into what's shown as "thinking" text.
  - The final parsed Action and "reason" (the THINKING sentence) are correct.
  - A connection error still falls back cleanly (unchanged from before).

Run directly: python3 tests/streaming_ai_test.py
"""
import http.server
import json
import os
import socketserver
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.ollama_client import OllamaClient, OllamaError
from ai.enemy_ai import make_enemy_ai_fn
from engine.actions import Action
from engine.battle import BattleEngine
from data.characters import make_party
from data.enemies import make_enemy_group
from data.items_db import ITEMS, STARTING_INVENTORY
from data.skills_db import SKILLS


class _StreamingFakeOllama(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"  # connection-close-terminated; no chunked encoding needed

    def log_message(self, *_args):
        pass

    def do_GET(self):
        body = json.dumps({"models": [{"model": "fake-model"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length))
        assert req["stream"] is True, "enemy AI must request streaming"
        assert "format" not in req, "streaming path must not set format=json (blocks free-text THINKING)"
        assert req["think"] is False, "must ask Ollama to skip extended reasoning (see empty-response bug)"
        assert req["options"]["num_predict"] == 42, req["options"]
        assert req["keep_alive"] == "5m", req

        user_msg = req["messages"][1]["content"]
        payload = json.loads(user_msg.split("Battle state (JSON):")[1].split("\n\nChoose")[0])
        skill_id = payload["available_skills"][0]["id"]
        target_id = payload["human_party_targets"][0]["id"]
        full_reply = (
            "THINKING: The mage looks vulnerable, striking now.\n"
            f'ACTION_JSON: {{"action": "skill", "skill_id": "{skill_id}", "target_id": "{target_id}"}}'
        )
        chunk_size = 6  # deliberately small/misaligned so label and marker straddle chunk boundaries
        chunks = [full_reply[i:i + chunk_size] for i in range(0, len(full_reply), chunk_size)]

        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for c in chunks:
            line = json.dumps({"model": req["model"], "message": {"role": "assistant", "content": c}, "done": False})
            self.wfile.write((line + "\n").encode())
            self.wfile.flush()
            time.sleep(0.02)
        done_line = json.dumps({"model": req["model"], "message": {"role": "assistant", "content": ""}, "done": True})
        self.wfile.write((done_line + "\n").encode())
        self.wfile.flush()


def test_live_streaming_pipeline():
    server = socketserver.TCPServer(("127.0.0.1", 0), _StreamingFakeOllama)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        events = []
        client = OllamaClient(host=f"http://127.0.0.1:{port}", model="fake-model", timeout=5,
                               num_predict=42, keep_alive="5m")
        get_enemy_action = make_enemy_ai_fn(client, use_fallback_on_error=True, on_decision=events.append)

        party, enemies = make_party(), make_enemy_group()
        engine = BattleEngine(
            party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
            inventory=dict(STARTING_INVENTORY),
            get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=get_enemy_action,
        )
        actor = enemies[0]
        state = engine.build_state(for_actor=actor)
        action = get_enemy_action(actor, state)

        phases = [e["phase"] for e in events]
        assert phases[0] == "start" and phases[-1] == "done"
        chunk_events = [e for e in events if e["phase"] == "thinking_chunk"]
        assert len(chunk_events) >= 3, f"expected multiple live thinking_chunk events, got {len(chunk_events)}"

        prev_len = -1
        for e in chunk_events:
            text = e["text_so_far"]
            assert len(text) >= prev_len, f"live text shrank: was {prev_len} chars, now {text!r}"
            prev_len = len(text)
            assert "ACTION_JSON" not in text.upper(), f"JSON marker leaked into thinking text: {text!r}"
            assert "{" not in text, f"JSON leaked into thinking text: {text!r}"
            assert not text.upper().startswith("THINKING"), f"label leaked into thinking text: {text!r}"

        final_seen = chunk_events[-1]["text_so_far"].strip()
        assert final_seen == "The mage looks vulnerable, striking now.", final_seen

        done = events[-1]
        assert done["used_fallback"] is False
        assert done["reason"].strip() == "The mage looks vulnerable, striking now."
        assert done["action_type"] == "skill"
        assert action.type.value == "skill"
        print(f"test_live_streaming_pipeline: PASS ({len(chunk_events)} chunk events, "
              f"final text={final_seen!r})")
    finally:
        server.shutdown()


class _ReasoningOnlyFakeOllama(http.server.BaseHTTPRequestHandler):
    """Simulates a reasoning-capable model (deepseek-r1/qwq/gpt-oss-style) that
    ignores our think=False request and burns its whole reply on internal
    chain-of-thought, streamed into message.thinking, leaving message.content
    empty. This is the exact failure Andrew hit against a real model: a real
    ~16s response came back, but with nothing in "content" -- previously
    surfaced as a baffling generic "empty streamed response" error. See
    OllamaClient.chat_stream's reasoning_chars tracking for the fix.
    """
    protocol_version = "HTTP/1.0"

    def log_message(self, *_args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        req = json.loads(self.rfile.read(length))
        assert req["think"] is False, req  # we do ask nicely; this fake just doesn't listen
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.end_headers()
        for chunk in ["Let me consider", " the battlefield...", " weighing my options."]:
            line = json.dumps({"model": req["model"],
                                "message": {"role": "assistant", "content": "", "thinking": chunk},
                                "done": False})
            self.wfile.write((line + "\n").encode())
        done_line = json.dumps({"model": req["model"], "message": {"role": "assistant", "content": ""},
                                 "done": True, "done_reason": "length"})
        self.wfile.write((done_line + "\n").encode())


def test_reasoning_model_gets_a_diagnostic_error_not_a_generic_one():
    server = socketserver.TCPServer(("127.0.0.1", 0), _ReasoningOnlyFakeOllama)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = OllamaClient(host=f"http://127.0.0.1:{port}", model="fake-reasoning-model", timeout=5)
        try:
            client.chat_stream("sys", "user")
            raise AssertionError("expected OllamaError")
        except OllamaError as exc:
            msg = str(exc).lower()
            assert "reasoning" in msg and "fake-reasoning-model" in str(exc), exc
            print(f"test_reasoning_model_gets_a_diagnostic_error_not_a_generic_one: PASS ({exc})")
    finally:
        server.shutdown()


def test_fallback_still_works_on_connection_error():
    """Unchanged behavior check: streaming's error paths must still degrade to
    the scripted fallback exactly like the old non-streaming path did."""
    client = OllamaClient(host="http://localhost:1", model="unreachable", timeout=0.5)
    events = []
    get_enemy_action = make_enemy_ai_fn(client, use_fallback_on_error=True, on_decision=events.append)
    party, enemies = make_party(), make_enemy_group()
    engine = BattleEngine(
        party=party, enemies=enemies, skills_db=SKILLS, items_db=ITEMS,
        inventory=dict(STARTING_INVENTORY),
        get_party_action=lambda c, s: Action.defend(c.id), get_enemy_action=get_enemy_action,
    )
    actor = enemies[0]
    state = engine.build_state(for_actor=actor)
    action = get_enemy_action(actor, state)
    assert isinstance(action, Action)
    done = events[-1]
    assert done["phase"] == "done" and done["used_fallback"] is True
    assert not any(e["phase"] == "thinking_chunk" for e in events), "no chunks should stream on a connection error"
    print("test_fallback_still_works_on_connection_error: PASS")


def main():
    test_live_streaming_pipeline()
    test_reasoning_model_gets_a_diagnostic_error_not_a_generic_one()
    test_fallback_still_works_on_connection_error()
    print("\nALL STREAMING AI TESTS PASSED")


if __name__ == "__main__":
    main()
