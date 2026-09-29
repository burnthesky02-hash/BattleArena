"""A minimal client for a locally-running Ollama server.

Deliberately small: this game only needs one call shape (chat), so we don't
pull in the full ollama-python SDK -- just `requests` against Ollama's REST
API. Two ways to make that call:
  - chat_json: non-streaming, `format: "json"` -- the whole reply arrives at
    once, already guaranteed-parseable JSON. Simple, but nothing to show
    while it's in flight.
  - chat_stream: streaming, plain text -- content arrives token-by-token as
    Ollama generates it, which is what lets debug mode show the model
    "typing" live. See ai/enemy_ai.py for how the two get used.
"""
import json
import time

import requests


class OllamaError(Exception):
    """Raised for any failure talking to Ollama or parsing its response.
    Callers (see ai/enemy_ai.py) should catch this and fall back gracefully.
    """


def _error_detail_from_response(resp) -> str:
    detail = resp.text[:300]
    try:
        detail = resp.json().get("error", detail)
    except ValueError:
        pass
    return detail


def _raise_for_status(resp, model: str) -> None:
    if resp.status_code == 200:
        return
    # Ollama reports an unknown/not-pulled model as 404 with an "error" field,
    # but different versions have used other codes for this too -- so surface
    # the error body rather than assuming the status code alone.
    detail = _error_detail_from_response(resp)
    if resp.status_code == 404 or "not found" in detail.lower():
        raise OllamaError(
            f"Model '{model}' not found on {resp.url} ({detail}). "
            f"Run `ollama list` to see exact model names, then pass --model <name> "
            f"(or `ollama pull {model}` if it's genuinely missing)."
        )
    raise OllamaError(f"Ollama returned HTTP {resp.status_code}: {detail}")


class OllamaClient:
    def __init__(self, host: str, model: str, timeout: float = 20.0,
                 num_predict: int = 200, keep_alive: str = "10m"):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        # Capping generation length bounds worst-case latency (a model that
        # would otherwise ramble past what we need); keep_alive tells Ollama
        # to keep the model loaded in memory between calls so consecutive
        # enemy turns don't each eat a reload penalty. Both are speed levers,
        # not just correctness ones -- see main.py/config.py for how to tune.
        self.num_predict = num_predict
        self.keep_alive = keep_alive

    def is_available(self) -> bool:
        """Quick reachability check, e.g. for a startup banner."""
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=min(5.0, self.timeout))
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list:
        """Returns the list of model tags Ollama actually has pulled (e.g.
        ["llama3.1:latest", "gemma3:27b"]), or [] if the server can't be reached.
        Used for a friendly startup check -- see main.py -- since the single
        most common "it's not reaching the model" cause is a model-name
        mismatch (missing/extra ":latest" tag, typo, or a model that was
        never actually pulled).
        """
        try:
            resp = requests.get(f"{self.host}/api/tags", timeout=min(5.0, self.timeout))
            resp.raise_for_status()
            data = resp.json()
            return [m.get("model") or m.get("name") for m in data.get("models", [])]
        except (requests.RequestException, ValueError, KeyError):
            return []

    def _options(self, temperature: float) -> dict:
        return {"temperature": temperature, "num_predict": self.num_predict}

    def warm_up(self) -> float:
        """Forces Ollama to load this model into memory right now, without
        generating anything, and returns how long that took (seconds).

        Why this exists: loading a large model's weights (especially 20B+
        ones like gemma3:27b) can itself take anywhere from several seconds
        to a couple of minutes depending on disk speed / RAM / whether it's
        offloaded to GPU -- and NONE of that time produces any streamed
        output, since the model isn't even in memory yet to start prefill.
        Without a warm-up, that entire load penalty lands on whichever
        enemy turn happens to go first, which is exactly what shows up in
        debug mode as being "stuck" at "(waiting for first token...)" --
        it's not stuck, it's genuinely still loading, it's just that a
        60-120s in-battle timeout can be shorter than a cold load takes.

        Calling this once at startup (see main.py) pays that cost with a
        clear "loading model..." message before the battle even begins,
        with a generous timeout of its own, so in-battle turns only ever
        hit the fast "already warm" path (as long as keep_alive doesn't
        expire between turns -- see config.OLLAMA_KEEP_ALIVE).

        Uses Ollama's documented trick for this: POST /api/generate with no
        `prompt` field loads the model and returns immediately once it's
        ready, without generating any tokens.
        """
        start = time.perf_counter()
        # Loading a large model from a slow disk can genuinely take minutes;
        # this uses its own generous timeout independent of self.timeout,
        # which is sized for normal (already-warm) in-battle calls instead.
        load_timeout = max(self.timeout, 300.0)
        try:
            resp = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "keep_alive": self.keep_alive},
                timeout=load_timeout,
            )
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                f"Ollama at {self.host} took longer than {load_timeout:.0f}s to load '{self.model}'."
            ) from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama request failed while loading '{self.model}': {exc}") from exc

        _raise_for_status(resp, self.model)
        return time.perf_counter() - start

    def chat_json(self, system_prompt: str, user_prompt: str, temperature: float = 0.7) -> dict:
        """Sends a non-streaming chat request and parses the whole reply as JSON.

        Uses Ollama's `format: "json"` option, which constrains the model's
        output to valid JSON. Simple and robust, but nothing is visible until
        the full response lands -- see chat_stream for the version debug mode
        uses so it can show the model "typing" live.
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "keep_alive": self.keep_alive,
            "think": False,  # see chat_stream's docstring for why
            "options": self._options(temperature),
        }
        try:
            resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout)
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(f"Ollama at {self.host} timed out after {self.timeout}s.") from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        _raise_for_status(resp, self.model)

        try:
            body = resp.json()
            content = body["message"]["content"]
        except (ValueError, KeyError) as exc:
            raise OllamaError(f"Unexpected Ollama response shape: {resp.text[:200]}") from exc

        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaError(f"Ollama did not return valid JSON: {content[:200]}") from exc

    def chat_stream(self, system_prompt: str, user_prompt: str, emit=None, temperature: float = 0.7) -> str:
        """Sends a STREAMING chat request and returns the full accumulated text.

        Ollama's streaming `/api/chat` sends one JSON object per line as
        generation proceeds, each carrying the next chunk of text in
        `message.content`. We don't use `format: "json"` here -- that mode
        constrains the *entire* output to be a JSON document, which would
        rule out a natural-language "thinking out loud" prefix. Instead
        ai/enemy_ai.py's prompt asks the model to write a THINKING: line
        followed by an ACTION_JSON: line, and parses that structure back out
        of the accumulated text once streaming finishes.

        `emit`, if given, is called with each text chunk as it arrives --
        this is the hook that makes the "model is typing" display possible.
        It's called synchronously from this (usually background) thread; see
        ai/enemy_ai.py's _run_streaming_with_relay for how callers safely
        hand chunks back to a main-thread UI like pygame.

        `think: False` is set deliberately. Several newer Ollama-served
        models (reasoning/"thinking" models such as deepseek-r1, qwq,
        magistral, gpt-oss, and some others depending on how they were
        pulled/configured) do extended internal reasoning by default,
        streamed into a separate `message.thinking` field rather than
        `message.content` -- and that reasoning can easily burn through the
        entire `num_predict` token budget before any real `content` is
        produced at all, which surfaces here as "Ollama returned an empty
        streamed response" even though the model genuinely ran for several
        seconds. We want the model's THINKING: line itself to be the
        visible reasoning, not a second hidden reasoning pass underneath
        it, so we explicitly turn that off. (Harmless no-op for any model
        that doesn't support the option.)
        """
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,
            "keep_alive": self.keep_alive,
            "think": False,
            "options": self._options(temperature),
        }
        try:
            resp = requests.post(f"{self.host}/api/chat", json=payload, timeout=self.timeout, stream=True)
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Could not reach Ollama at {self.host}. Is `ollama serve` running?"
            ) from exc
        except requests.exceptions.Timeout as exc:
            raise OllamaError(f"Ollama at {self.host} timed out after {self.timeout}s.") from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        if resp.status_code != 200:
            _raise_for_status(resp, self.model)

        chunks = []
        reasoning_chars = 0  # see the empty-response diagnosis below
        done_reason = None
        try:
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue  # skip any stray non-JSON line rather than failing the whole turn
                if obj.get("error"):
                    raise OllamaError(f"Ollama error mid-stream: {obj['error']}")
                message = obj.get("message", {})
                content = message.get("content", "")
                if content:
                    chunks.append(content)
                    if emit:
                        emit(content)
                # Some reasoning-capable models stream their internal chain-of-thought
                # into `message.thinking` instead of `message.content`. We ask Ollama
                # not to do this (`think: False` above), but track it anyway in case a
                # particular model/Ollama version doesn't honor that -- it turns a
                # baffling "empty response" into an actionable error message below.
                reasoning_chars += len(message.get("thinking") or "")
                if obj.get("done"):
                    done_reason = obj.get("done_reason")
                    break
        except requests.exceptions.RequestException as exc:
            raise OllamaError(f"Ollama stream was interrupted: {exc}") from exc

        full_text = "".join(chunks)
        if not full_text.strip():
            if reasoning_chars:
                raise OllamaError(
                    f"Ollama spent its whole reply on internal reasoning ({reasoning_chars} "
                    f"chars in message.thinking) and produced no actual THINKING:/ACTION_JSON: "
                    f"text -- '{self.model}' looks like a reasoning model that isn't honoring "
                    f"think=False. Try a non-reasoning model, or raise OLLAMA_NUM_PREDICT well "
                    f"past its typical reasoning length."
                )
            if done_reason == "length":
                raise OllamaError(
                    f"Ollama returned an empty streamed response and hit the {self.num_predict}-token "
                    f"limit (OLLAMA_NUM_PREDICT) before producing any content -- try raising it."
                )
            raise OllamaError("Ollama returned an empty streamed response.")
        return full_text
