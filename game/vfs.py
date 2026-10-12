"""Read-only virtual file system for the packaged demo.

The demo ships its web pages, scene data, art and audio inside one encrypted pack (game.pak) instead of loose files.
`root(name, project_root)` returns a PakPath for that folder when the pack is mounted, otherwise a normal pathlib.Path,
so hub_server.py reads files the same way in both cases. PakPath supports only what the server uses
(/, resolve, parents, name/stem/suffix, is_file/is_dir/exists, read_bytes/read_text, iterdir, glob("*.ext")).

Pack format: MAGIC | index offset (8) | index length (8) | index nonce (16) | file blobs ... | index.
Every blob (and the index) is XORed with a SHAKE-256 keystream of key+nonce; text-like files are zlib-compressed first."""
import hashlib
import json
import os
import posixpath
import threading
import zlib
from pathlib import Path

MAGIC = b"SKYPAK01"
_HEADER = len(MAGIC) + 8 + 8 + 16
_COMPRESS = {".json", ".js", ".html", ".css", ".txt", ".svg"}


def xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    n = len(data)
    if not n:
        return b""
    ks = hashlib.shake_256(key + nonce).digest(n)
    return (int.from_bytes(data, "little") ^ int.from_bytes(ks, "little")).to_bytes(n, "little")


def write_pak(out_path, entries, key: bytes) -> int:
    """entries: iterable of (archive path with '/', bytes-or-source-file-path). Returns the number of files packed."""
    index = {}
    with open(out_path, "wb") as f:
        f.write(b"\0" * _HEADER)
        for arc, src in entries:
            raw = src if isinstance(src, (bytes, bytearray)) else Path(src).read_bytes()
            z = os.path.splitext(arc)[1].lower() in _COMPRESS
            body = zlib.compress(bytes(raw), 9) if z else bytes(raw)
            nonce = os.urandom(16)
            off = f.tell()
            f.write(xor_stream(body, key, nonce))
            index[arc] = [off, len(body), len(raw), nonce.hex(), 1 if z else 0]
        raw_index = zlib.compress(json.dumps(index).encode("utf-8"), 9)
        inonce = os.urandom(16)
        ioff = f.tell()
        f.write(xor_stream(raw_index, key, inonce))
        ilen = f.tell() - ioff
        f.seek(0)
        f.write(MAGIC + ioff.to_bytes(8, "little") + ilen.to_bytes(8, "little") + inonce)
    return len(index)


class Pak:
    def __init__(self, path, key: bytes):
        self._f = open(path, "rb")
        self._key = key
        self._lock = threading.Lock()
        head = self._f.read(_HEADER)
        if head[:len(MAGIC)] != MAGIC:
            raise ValueError("not a game pack")
        ioff = int.from_bytes(head[8:16], "little")
        ilen = int.from_bytes(head[16:24], "little")
        inonce = head[24:40]
        self._f.seek(ioff)
        self.index = json.loads(zlib.decompress(xor_stream(self._f.read(ilen), key, inonce)))
        self._dirs = {""}
        for p in self.index:
            d = posixpath.dirname(p)
            while d and d not in self._dirs:
                self._dirs.add(d)
                d = posixpath.dirname(d)
        # Windows file names are case-insensitive and the game's URLs rely on that ("/assets/title/..." for a folder called
        # "Title"), so the pack answers the same way: look names up in lower case, hand back the stored spelling.
        self._ci_files = {k.lower(): k for k in self.index}
        self._ci_dirs = {d.lower(): d for d in self._dirs}
        self._cache = {}          # recently read big files (audio/video are fetched in many ranges)
        self._cache_bytes = 0

    def has(self, p): return p.lower() in self._ci_files
    def isdir(self, p): return p.lower() in self._ci_dirs

    def read(self, p) -> bytes:
        p = self._ci_files.get(p.lower(), p)
        ent = self.index.get(p)
        if ent is None:
            raise FileNotFoundError(p)
        hit = self._cache.get(p)
        if hit is not None:
            return hit
        off, stored, _raw, nonce, z = ent
        with self._lock:
            self._f.seek(off)
            blob = self._f.read(stored)
        data = xor_stream(blob, self._key, bytes.fromhex(nonce))
        if z:
            data = zlib.decompress(data)
        if len(data) > 262144:
            with self._lock:
                while self._cache and self._cache_bytes + len(data) > 64 * 1024 * 1024:
                    k = next(iter(self._cache))
                    self._cache_bytes -= len(self._cache.pop(k))
                self._cache[p] = data
                self._cache_bytes += len(data)
        return data

    def children(self, p):
        p = self._ci_dirs.get(p.lower(), p)
        pre = p + "/" if p else ""
        seen = set()
        for k in list(self.index) + list(self._dirs):
            if k and k.startswith(pre) and k != p:
                seen.add(pre + k[len(pre):].split("/", 1)[0])
        return sorted(seen)


_pak = None


def mount(pak_path, key: bytes) -> bool:
    global _pak
    try:
        _pak = Pak(pak_path, key)
        return True
    except (OSError, ValueError, KeyError, zlib.error):
        _pak = None
        return False


def mounted() -> bool:
    return _pak is not None


def _norm(p: str) -> str:
    p = posixpath.normpath(str(p).replace("\\", "/"))
    return "" if p == "." else p.lstrip("/")


class PakPath:
    __slots__ = ("_p",)

    def __init__(self, p: str = ""):
        self._p = _norm(p)

    def __truediv__(self, other): return PakPath(self._p + "/" + str(other))
    def resolve(self): return self
    def __eq__(self, other): return isinstance(other, PakPath) and other._p == self._p
    def __hash__(self): return hash(self._p)
    def __lt__(self, other): return isinstance(other, PakPath) and self._p < other._p        # sorted(folder.iterdir()) must work like it does on a real Path
    def __gt__(self, other): return isinstance(other, PakPath) and self._p > other._p
    def __le__(self, other): return isinstance(other, PakPath) and self._p <= other._p
    def __ge__(self, other): return isinstance(other, PakPath) and self._p >= other._p
    def __str__(self): return self._p
    def __repr__(self): return "PakPath(%r)" % self._p
    def __fspath__(self): raise OSError("packed file has no real path")

    @property
    def name(self): return posixpath.basename(self._p)
    @property
    def suffix(self): return posixpath.splitext(self._p)[1]
    @property
    def stem(self): return posixpath.splitext(posixpath.basename(self._p))[0]
    @property
    def parent(self): return PakPath(posixpath.dirname(self._p))
    @property
    def parents(self):
        out, d = [], posixpath.dirname(self._p)
        while d:
            out.append(PakPath(d))
            d = posixpath.dirname(d)
        return out

    def is_file(self): return _pak is not None and _pak.has(self._p)
    def is_dir(self): return _pak is not None and _pak.isdir(self._p)
    def exists(self): return self.is_file() or self.is_dir()
    def read_bytes(self):
        if _pak is None:
            raise FileNotFoundError(self._p)
        return _pak.read(self._p)
    def read_text(self, encoding="utf-8", errors="strict"): return self.read_bytes().decode(encoding, errors)
    def iterdir(self): return iter([PakPath(c) for c in (_pak.children(self._p) if _pak else [])])
    def glob(self, pattern):
        ext = pattern[1:] if pattern.startswith("*") else None
        for c in self.iterdir():
            if (ext is not None and c._p.endswith(ext) and c.is_file()) or (ext is None and c.name == pattern):
                yield c


def root(name: str, project_root: Path):
    return PakPath(name) if _pak is not None else Path(project_root) / name
