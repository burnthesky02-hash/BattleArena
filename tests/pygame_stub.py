"""A minimal fake `pygame` module, used only so ui/pygame_ui.py's control
flow (menu building, target selection, event handling) can be exercised in
this sandbox, which has no network access to actually install pygame/SDL.

This is NOT a pygame reimplementation -- it's just enough surface area for
PygameUI to run without raising AttributeError, with a scriptable event
queue so a test can simulate mouse clicks deterministically. Real rendering
correctness still needs a human to look at the actual window (see README).
"""
import types


class Rect:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    def collidepoint(self, pos):
        px, py = pos
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def __repr__(self):
        return f"Rect({self.x},{self.y},{self.w},{self.h})"


class SurfaceStub:
    def __init__(self, size=(0, 0), flags=0):
        # `flags` (e.g. pygame.SRCALPHA, used by fix #18's per-pixel-alpha
        # translucent panels) is accepted but unused -- this stub never
        # actually blends pixels, it just needs to not raise on the extra
        # positional/keyword arg real pygame's Surface() accepts.
        self._size = size

    def fill(self, color):
        pass

    def blit(self, surface, pos):
        pass

    def set_alpha(self, a):
        pass

    def get_width(self):
        return self._size[0] or 80

    def get_height(self):
        return self._size[1] or 16

    def convert_alpha(self):
        return self

    def subsurface(self, area):
        # area is (x, y, w, h) here (pygame_ui.py never passes a Rect); real
        # pygame would share pixel data with the parent, but nothing in this
        # stub reads pixels, so a plain same-sized stand-in is enough.
        _, _, w, h = area
        return SurfaceStub((w, h))

    def copy(self):
        return SurfaceStub(self._size)


class FontStub:
    def __init__(self, name=None, size=16, bold=False):
        self.size = size

    def render(self, text, antialias, color):
        return SurfaceStub((max(1, len(text)) * (self.size // 2 + 2), self.size))


class ClockStub:
    def tick(self, fps):
        return 0


class Event:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_pygame_stub(event_queue):
    """event_queue: a list this stub will pop events from (front to back),
    one event per call to event.get() -- see the module docstring for why.
    """
    pg = types.ModuleType("pygame")
    pg.QUIT = 1
    pg.KEYDOWN = 2
    pg.MOUSEBUTTONDOWN = 3
    pg.MOUSEWHEEL = 4
    pg.K_ESCAPE = 27
    pg.K_BACKSPACE = 8
    pg.K_RETURN = 13
    # Arbitrary bit flags -- just need to exist and be OR-able, same as real
    # pygame's (values themselves don't matter to anything in this stub).
    pg.FULLSCREEN = 1 << 0
    pg.SCALED = 1 << 1
    pg.SRCALPHA = 1 << 2
    pg.Rect = Rect
    pg.Surface = SurfaceStub
    pg.Event = Event

    pg.init = lambda: None
    pg.quit = lambda: setattr(pg, "_quit_called", True)
    pg._quit_called = False

    display = types.SimpleNamespace(
        set_mode=lambda size, flags=0: SurfaceStub(size),
        set_caption=lambda title: None,
        flip=lambda: None,
    )
    pg.display = display

    def sysfont(name, size, bold=False):
        return FontStub(name, size, bold)

    pg.font = types.SimpleNamespace(SysFont=sysfont)

    def draw_rect(surface, color, rect, width=0, border_radius=0):
        pass

    def draw_circle(surface, color, center, radius, width=0):
        pass

    def draw_polygon(surface, color, points, width=0):
        pass
    pg.draw = types.SimpleNamespace(rect=draw_rect, circle=draw_circle, polygon=draw_polygon)

    pg.time = types.SimpleNamespace(Clock=lambda: ClockStub(), delay=lambda ms: None)

    def event_get():
        if event_queue:
            return [event_queue.pop(0)]
        return []
    pg.event = types.SimpleNamespace(get=event_get)

    pg.mouse = types.SimpleNamespace(get_pos=lambda: (0, 0))

    # Just enough of pygame.image/pygame.transform for ui/pygame_ui.py's
    # hero-portrait loading (_get_portrait) and battle sprite-sheet loading
    # (_load_battler_sheet_raw/_get_battler_frames) to exercise their "found
    # a file" branches in a test -- load() returns a same-sized stub surface
    # rather than actually decoding anything. 72x72 (not a real sheet's
    # actual dimensions) is just a size that divides evenly by
    # BATTLER_FRAME_COLS/ROWS (6x6) so slicing it doesn't need to worry about
    # remainder pixels. smoothscale/scale just relabel the requested size,
    # and flip returns a same-sized surface too (marked ._flipped_x so a test
    # can tell a mirrored frame apart from an unmirrored one) -- all matching
    # real pygame's return-a-new-surface shape without actually transforming
    # any pixels.
    pg.image = types.SimpleNamespace(load=lambda path: SurfaceStub((72, 72)))

    def transform_flip(surface, xbool, ybool):
        flipped = SurfaceStub(surface._size)
        flipped._flipped_x = bool(xbool) != bool(getattr(surface, "_flipped_x", False))
        return flipped

    pg.transform = types.SimpleNamespace(
        smoothscale=lambda surface, size: SurfaceStub(size),
        scale=lambda surface, size: SurfaceStub(size),
        flip=transform_flip,
    )

    return pg
