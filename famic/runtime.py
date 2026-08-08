"""The 6502 runtime library.

Everything an NES game needs 6502 skill for lives here: the OAM transfer, the
VRAM write window, attribute read-modify-write, metasprite and metatile
expansion, scrolling, the sound drivers.  A FAMI-C program calls these by name
and never writes assembly.

Modules are pulled in on demand.  `needs=("oam",)` on a builtin in api.py is
the only thing that decides whether the sprite code lands in the ROM -- there
is no declaration an agent has to get exactly right to switch a feature on.

Conventions
-----------
* 8-bit values are passed and returned in A.
* 16-bit values are A = low byte, `__ah` = high byte.
* Arguments live in fixed labels `__a_<function>_<param>`, written by the
  caller before `JSR`.  No stack frames, no recursion.
* Every routine here owns named zero-page scratch (`__v_*`, `__at_*`, ...).
  Nothing in the runtime borrows the code generator's `__t0..__t5`, so a
  runtime call can never clobber a half-evaluated expression.

Screen model
------------
Vertical mirroring puts the two nametables side by side, so background
coordinates span both: tile x is 0..63, and 16x16 cell x is 0..31.  x < 32 is
the left screen, x >= 32 the right one.  That is what makes `scroll_set()`
usable for a horizontally scrolling game without any extra concepts.
"""

from __future__ import annotations

from typing import Dict, List, Sequence, Set

from .api import BY_NAME
from .assets import CompiledAssets, NOTE_PERIODS


VRAM_QUEUE_SIZE = 64
VRAM_PER_FRAME = 32

MODULE_DEPS: Dict[str, Sequence[str]] = {
    "vram": (),
    "attr": ("vram",),
    "metatile": ("vram", "attr"),
    "map": ("vram", "attr", "metatile"),
    "font": ("vram",),
    "bcd": ("vram", "font"),
    "oam": (),
    "metasprite": ("oam",),
    "scroll": (),
    "palette": (),
    "pad": (),
    "rand": (),
    "mul": (),
    "div": (),
    "collision": (),
    "sfx": ("notes",),
    "music": ("notes",),
    "notes": (),
}


def resolve_modules(requested: Set[str]) -> Set[str]:
    out: Set[str] = set()
    pending = list(requested)
    while pending:
        name = pending.pop()
        if name in out:
            continue
        out.add(name)
        pending.extend(MODULE_DEPS.get(name, ()))
    return out


def modules_for_calls(called: Set[str]) -> Set[str]:
    needed: Set[str] = set()
    for name in called:
        builtin = BY_NAME.get(name)
        if builtin:
            needed.update(builtin.needs)
    return resolve_modules(needed)


def emitted_builtins(modules: Set[str]) -> List[str]:
    """Builtins whose routine lands in the ROM for this module set.

    Argument slots have to be allocated for all of them, not just the ones the
    program calls, because the runtime routines reference each other's slots
    (spr_meta writes spr_meta_flip's arguments, for instance).
    """

    out: List[str] = []
    for name, builtin in BY_NAME.items():
        if set(builtin.needs) <= modules:
            out.append(name)
    return out


class Runtime:
    def __init__(self, modules: Set[str], assets: CompiledAssets):
        self.m = modules
        self.assets = assets
        self.lines: List[str] = []

    def emit(self, *lines: str) -> None:
        self.lines.extend(lines)

    def has(self, name: str) -> bool:
        return name in self.m

    @property
    def render_mask(self) -> str:
        """$2001 while rendering: background always, sprites only if used."""

        return "$1E" if self.has("oam") else "$0E"

    # ------------------------------------------------------------------
    # RAM map
    # ------------------------------------------------------------------

    def ram_declarations(self) -> List[str]:
        out: List[str] = []
        # Code generator scratch.
        out += [".zp __ptr 2", ".zp __ptr2 2", ".zp __ah 1", ".zp __rl 1", ".zp __rh 1"]
        out += [f".zp __t{i} 1" for i in range(6)]
        # Runtime scratch, never touched by generated expression code.
        out += [".zp __rp 2", ".zp __rp2 2"]
        out += [".zp __nmi_flag 1", ".zp __frame 1", ".zp __rendering 1", ".zp __vram_lock 1"]
        if self.has("vram"):
            out += [
                ".zp __vq_head 1",
                ".zp __vq_tail 1",
                ".zp __v_lo 1",
                ".zp __v_hi 1",
                ".zp __v_data 1",
                ".zp __v_x 1",
                ".zp __v_y 1",
                ".zp __rc_x 1",
                ".zp __rc_y 1",
                ".zp __rc_w 1",
                ".zp __rc_h 1",
                ".zp __rc_t 1",
                ".zp __run_len 1",
                ".zp __run_i 1",
            ]
        if self.has("attr"):
            out += [
                ".zp __at_idx 1",
                ".zp __at_shift 1",
                ".zp __at_val 1",
                ".zp __at_pal 1",
                ".zp __at_cx 1",
                ".zp __at_cy 1",
            ]
        if self.has("metatile"):
            out += [".zp __mt_x 1", ".zp __mt_y 1", ".zp __mt_id 1"]
        if self.has("map"):
            out += [".zp __mp_w 1", ".zp __mp_h 1", ".zp __mp_cx 1", ".zp __mp_cy 1", ".zp __mp_i 1"]
        if self.has("bcd"):
            out += [".zp __nm_i 1", ".zp __nm_p 1", ".zp __nm_d 1", ".zp __nm_n 1"]
            out += [".zp __nm_lo 1", ".zp __nm_hi 1"]
        if self.has("oam"):
            out += [
                ".zp __oam_index 1",
                ".zp __sp_x 1",
                ".zp __sp_y 1",
                ".zp __sp_t 1",
                ".zp __sp_a 1",
            ]
        if self.has("metasprite"):
            out += [".zp __ms_i 1", ".zp __ms_dx 1"]
        if self.has("scroll"):
            out += [".zp __scroll_x_lo 1", ".zp __scroll_x_hi 1", ".zp __scroll_y 1"]
        if self.has("palette"):
            out += [
                ".zp __pal_dirty 1",
                ".zp __pal_bright 1",
                ".zp __pd_in 1",
                ".zp __pd_t 1",
                ".zp __pd_dim 1",
            ]
        if self.has("rand"):
            out += [".zp __rng_lo 1", ".zp __rng_hi 1"]
        if self.has("sfx"):
            out += [".zp __sfx_pos 1", ".zp __sfx_left 1"]
        if self.has("music"):
            out += [
                ".zp __mus_ptr 2",
                ".zp __mus_playing 1",
                ".zp __mus_speed 1",
                ".zp __mus_timer 1",
                ".zp __mus_left_lo 1",
                ".zp __mus_left_hi 1",
                ".zp __mus_base_lo 1",
                ".zp __mus_base_hi 1",
                ".zp __mus_rows_lo 1",
                ".zp __mus_rows_hi 1",
            ]
        # Larger blocks go in general RAM.
        if self.has("vram"):
            out += [
                f".ram __vq_hi {VRAM_QUEUE_SIZE}",
                f".ram __vq_lo {VRAM_QUEUE_SIZE}",
                f".ram __vq_data {VRAM_QUEUE_SIZE}",
            ]
        if self.has("attr"):
            out.append(".ram __attr 128")
        if self.has("palette"):
            out.append(".ram __pal 32")
        if self.has("pad"):
            out += [
                ".ram __pad_held 2",
                ".ram __pad_prev 2",
                ".ram __pad_pressed 2",
                ".ram __pad_released 2",
            ]
        if self.has("bcd"):
            out.append(".ram __num_buf 5")
        return out

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_code(self) -> List[str]:
        self.lines = []
        self.emit(
            "_reset:",
            "SEI",
            "CLD",
            "LDX #$40",
            "STX $4017",
            "LDX #$FF",
            "TXS",
            "INX",
            "STX $2000",
            "STX $2001",
            "STX $4010",
            "__reset_vb1:",
            "BIT $2002",
            "BPL __reset_vb1",
            # Clear RAM so a power-on and a reset start from the same state.
            "LDA #$00",
            "TAX",
            "__reset_clear:",
            "STA $0000,X",
            "STA $0300,X",
            "STA $0400,X",
            "STA $0500,X",
            "STA $0600,X",
            "STA $0700,X",
            "INX",
            "BNE __reset_clear",
            "__reset_vb2:",
            "BIT $2002",
            "BPL __reset_vb2",
        )
        if self.has("oam"):
            self.emit("JSR _spr_clear")
        if self.has("rand"):
            self.emit("LDA #$5A", "STA __rng_lo", "LDA #$A5", "STA __rng_hi")
        if self.has("palette"):
            self.emit("LDA #$04", "STA __pal_bright")
        if self.has("sfx") or self.has("music"):
            self.emit(
                "LDA #$0F",
                "STA $4015",
                "LDA #$30",
                "STA $4000",
                "STA $4004",
                "STA $400C",
                "LDA #$00",
                "STA $4008",
            )
        self.emit("JSR __clear_vram")
        self.emit("LDA #$01", "STA __rendering")
        # NMI on; both pattern tables at $0000 so a tile index means the same
        # thing to the background and to sprites.
        self.emit("LDA #$80", "STA $2000")
        self.emit(f"LDA #{self.render_mask}", "STA $2001")
        self.emit("JSR _f_main")
        self.emit("__forever:", "JMP __forever")
        return self.lines

    # ------------------------------------------------------------------
    # NMI
    # ------------------------------------------------------------------

    def nmi_code(self) -> List[str]:
        self.lines = []
        self.emit(
            "",
            "_nmi:",
            "PHA",
            "TXA",
            "PHA",
            "TYA",
            "PHA",
            "INC __frame",
            "LDA #$01",
            "STA __nmi_flag",
        )
        if self.has("oam"):
            self.emit(
                "LDA __rendering",
                "BEQ __nmi_no_oam",
                "LDA #$00",
                "STA $2003",
                "LDA #$02",
                "STA $4014",
                "__nmi_no_oam:",
            )
        # Main-line code holds __vram_lock while it drives $2006 directly, so
        # the NMI must not touch VRAM in that window.
        self.emit("LDA __vram_lock", "BEQ __nmi_vram_ok", "JMP __nmi_vram_done", "__nmi_vram_ok:")
        if self.has("palette"):
            self.emit("JSR __pal_upload")
        if self.has("vram"):
            self.emit("JSR __vq_drain")
        self.emit("__nmi_vram_done:")
        if self.has("scroll"):
            self.emit(
                "LDA $2002",
                "LDA __scroll_x_hi",
                "AND #$01",
                "ORA #$80",
                "STA $2000",
                "LDA __scroll_x_lo",
                "STA $2005",
                "LDA __scroll_y",
                "STA $2005",
            )
        else:
            self.emit("LDA $2002", "LDA #$00", "STA $2005", "STA $2005")
        if self.has("music"):
            self.emit("JSR __music_tick")
        if self.has("sfx"):
            self.emit("JSR __sfx_tick")
        self.emit("PLA", "TAY", "PLA", "TAX", "PLA", "RTI", "", "_irq:", "RTI")
        return self.lines

    # ------------------------------------------------------------------
    # Routines
    # ------------------------------------------------------------------

    def routines(self) -> List[str]:
        self.lines = []
        self._core()
        if self.has("vram"):
            self._vram()
        if self.has("attr"):
            self._attr()
        if self.has("metatile"):
            self._metatile()
        if self.has("map"):
            self._map()
        if self.has("font"):
            self._font()
        if self.has("bcd"):
            self._bcd()
        if self.has("oam"):
            self._oam()
        if self.has("metasprite"):
            self._metasprite()
        if self.has("scroll"):
            self._scroll()
        if self.has("palette"):
            self._palette()
        if self.has("pad"):
            self._pad()
        self._math()
        if self.has("rand"):
            self._rand()
        if self.has("collision"):
            self._collision()
        if self.has("sfx"):
            self._sfx()
        if self.has("music"):
            self._music()
        return self.lines

    # -- core --------------------------------------------------------------

    def _core(self) -> None:
        self.emit(
            "",
            "_wait_vblank:",
            "LDA #$00",
            "STA __nmi_flag",
            "__wait_vblank_loop:",
            "LDA __nmi_flag",
            "BEQ __wait_vblank_loop",
            "RTS",
            "",
            "_frame_count:",
            "LDA __frame",
            "RTS",
            "",
            "_ppu_off:",
            "LDA #$00",
            "STA __rendering",
            "STA $2001",
            "RTS",
            "",
            "_ppu_on:",
            "LDA #$01",
            "STA __rendering",
            f"LDA #{self.render_mask}",
            "STA $2001",
            "RTS",
            "",
            # Blank both nametables and both attribute tables.  Reset calls this
            # with rendering already off.
            "__clear_vram:",
            "INC __vram_lock",
            "LDA $2002",
            "LDA #$20",
            "STA $2006",
            "LDA #$00",
            "STA $2006",
            "LDX #$08",
            "LDA #$00",
            "__clear_vram_page:",
            "LDY #$00",
            "__clear_vram_byte:",
            "STA $2007",
            "INY",
            "BNE __clear_vram_byte",
            "DEX",
            "BNE __clear_vram_page",
            "DEC __vram_lock",
            "RTS",
        )

    # -- background --------------------------------------------------------

    def _vram(self) -> None:
        self.emit(
            "",
            # __v_lo/__v_hi = VRAM address, __v_data = byte.  Writes straight
            # through when rendering is off, queues otherwise, so calling code
            # never has to know which frame phase it is in.
            "__vram_put:",
            "LDA __rendering",
            "BNE __vram_put_queue",
            "INC __vram_lock",
            "LDA $2002",
            "LDA __v_hi",
            "STA $2006",
            "LDA __v_lo",
            "STA $2006",
            "LDA __v_data",
            "STA $2007",
            "DEC __vram_lock",
            "RTS",
            "__vram_put_queue:",
            "__vram_put_wait:",
            "LDX __vq_head",
            "INX",
            f"CPX #{VRAM_QUEUE_SIZE}",
            "BNE __vram_put_nowrap",
            "LDX #$00",
            "__vram_put_nowrap:",
            "CPX __vq_tail",
            "BEQ __vram_put_wait",
            "LDX __vq_head",
            "LDA __v_hi",
            "STA __vq_hi,X",
            "LDA __v_lo",
            "STA __vq_lo,X",
            "LDA __v_data",
            "STA __vq_data,X",
            "INX",
            f"CPX #{VRAM_QUEUE_SIZE}",
            "BNE __vram_put_store",
            "LDX #$00",
            "__vram_put_store:",
            "STX __vq_head",
            "RTS",
            "",
            "__vq_drain:",
            f"LDY #{VRAM_PER_FRAME}",
            "__vq_drain_loop:",
            "LDX __vq_tail",
            "CPX __vq_head",
            "BEQ __vq_drain_done",
            "LDA $2002",
            "LDA __vq_hi,X",
            "STA $2006",
            "LDA __vq_lo,X",
            "STA $2006",
            "LDA __vq_data,X",
            "STA $2007",
            "INX",
            f"CPX #{VRAM_QUEUE_SIZE}",
            "BNE __vq_drain_next",
            "LDX #$00",
            "__vq_drain_next:",
            "STX __vq_tail",
            "DEY",
            "BNE __vq_drain_loop",
            "__vq_drain_done:",
            "RTS",
            "",
            # __v_x (0-63), __v_y (0-29) -> __v_lo/__v_hi
            "__vram_addr:",
            "LDA __v_y",
            "AND #$07",
            "ASL A",
            "ASL A",
            "ASL A",
            "ASL A",
            "ASL A",
            "STA __v_lo",
            "LDA __v_x",
            "AND #$1F",
            "CLC",
            "ADC __v_lo",
            "STA __v_lo",
            "LDA __v_y",
            "LSR A",
            "LSR A",
            "LSR A",
            "CLC",
            "ADC #$20",
            "STA __v_hi",
            "LDA __v_x",
            "AND #$20",
            "BEQ __vram_addr_done",
            "LDA __v_hi",
            "CLC",
            "ADC #$04",
            "STA __v_hi",
            "__vram_addr_done:",
            "RTS",
            "",
            "_bg_tile:",
            "LDA __a_bg_tile_y",
            "CMP #30",
            "BCC __bg_tile_ok",
            "RTS",
            "__bg_tile_ok:",
            "STA __v_y",
            "LDA __a_bg_tile_x",
            "AND #$3F",
            "STA __v_x",
            "JSR __vram_addr",
            "LDA __a_bg_tile_tile",
            "STA __v_data",
            "JMP __vram_put",
            "",
            "_bg_rect:",
            "LDA __a_bg_rect_x",
            "STA __rc_x",
            "LDA __a_bg_rect_y",
            "STA __rc_y",
            "LDA __a_bg_rect_w",
            "STA __rc_w",
            "LDA __a_bg_rect_h",
            "STA __rc_h",
            "LDA __a_bg_rect_tile",
            "STA __rc_t",
            "__bg_rect_row:",
            "LDA __rc_h",
            "BEQ __bg_rect_done",
            "LDA __rc_y",
            "CMP #30",
            "BCS __bg_rect_done",
            "LDX __rc_w",
            "BEQ __bg_rect_next",
            "LDA __rc_x",
            "STA __v_x",
            "__bg_rect_col:",
            "LDA __rc_y",
            "STA __v_y",
            "LDA __v_x",
            "AND #$3F",
            "STA __v_x",
            "JSR __vram_addr",
            "LDA __rc_t",
            "STA __v_data",
            "TXA",
            "PHA",
            "JSR __vram_put",
            "PLA",
            "TAX",
            "INC __v_x",
            "DEX",
            "BNE __bg_rect_col",
            "__bg_rect_next:",
            "INC __rc_y",
            "DEC __rc_h",
            "JMP __bg_rect_row",
            "__bg_rect_done:",
            "RTS",
            "",
            # Bulk clear: 960 tiles then 64 attribute bytes, per nametable.
            # Rendering is switched off for the duration so this is one pass
            # instead of dozens of queued frames, then restored.
            "_bg_clear:",
            "LDA __rendering",
            "PHA",
            "LDA #$00",
            "STA $2001",
            "STA __rendering",
            "INC __vram_lock",
            "LDA #$20",
            "STA __v_hi",
            "JSR __bg_clear_screen",
            "LDA #$24",
            "STA __v_hi",
            "JSR __bg_clear_screen",
            "DEC __vram_lock",
        )
        if self.has("attr"):
            self.emit(
                "LDX #$00",
                "LDA #$00",
                "__bg_clear_shadow:",
                "STA __attr,X",
                "INX",
                "CPX #128",
                "BNE __bg_clear_shadow",
            )
        self.emit(
            "PLA",
            "STA __rendering",
            "BEQ __bg_clear_done",
            f"LDA #{self.render_mask}",
            "STA $2001",
            "__bg_clear_done:",
            "RTS",
            "",
            "__bg_clear_screen:",
            "LDA $2002",
            "LDA __v_hi",
            "STA $2006",
            "LDA #$00",
            "STA $2006",
            "LDX #$03",
            "__bg_clear_page:",
            "LDY #$00",
            "__bg_clear_byte:",
            "LDA __a_bg_clear_tile",
            "STA $2007",
            "INY",
            "BNE __bg_clear_byte",
            "DEX",
            "BNE __bg_clear_page",
            "LDY #192",
            "__bg_clear_tail:",
            "LDA __a_bg_clear_tile",
            "STA $2007",
            "DEY",
            "BNE __bg_clear_tail",
            "LDY #64",
            "LDA #$00",
            "__bg_clear_attr:",
            "STA $2007",
            "DEY",
            "BNE __bg_clear_attr",
            "RTS",
            "",
            "_bg_flush:",
            "LDA __vq_head",
            "CMP __vq_tail",
            "BNE _bg_flush",
            "RTS",
            "",
            # __v_x/__v_y = start, __rp = source address, __run_len = length.
            "__bg_run:",
            "LDA #$00",
            "STA __run_i",
            "__bg_run_loop:",
            "LDA __run_i",
            "CMP __run_len",
            "BEQ __bg_run_done",
            "TAY",
            "LDA (__rp),Y",
            "STA __v_data",
            "JSR __vram_addr",
            "JSR __vram_put",
            "INC __v_x",
            "INC __run_i",
            "JMP __bg_run_loop",
            "__bg_run_done:",
            "RTS",
        )

    def _attr(self) -> None:
        self.emit(
            "",
            # __at_idx gets the shadow index (0-127); the top bit picks the
            # nametable, the low six the attribute byte inside it.
            "__attr_index:",
            "LDA __at_cx",
            "AND #$0F",
            "LSR A",
            "STA __at_idx",
            "LDA __at_cy",
            "LSR A",
            "ASL A",
            "ASL A",
            "ASL A",
            "CLC",
            "ADC __at_idx",
            "STA __at_idx",
            "LDA __at_cx",
            "AND #$10",
            "BEQ __attr_index_nt0",
            "LDA __at_idx",
            "CLC",
            "ADC #$40",
            "STA __at_idx",
            "__attr_index_nt0:",
            "LDA __at_cy",
            "AND #$01",
            "ASL A",
            "ASL A",
            "STA __at_shift",
            "LDA __at_cx",
            "AND #$01",
            "ASL A",
            "CLC",
            "ADC __at_shift",
            "STA __at_shift",
            "RTS",
            "",
            # __at_cx / __at_cy = cell, __at_pal = palette 0-3
            "__attr_set:",
            "JSR __attr_index",
            "LDA #$03",
            "LDY __at_shift",
            "BEQ __attr_mask_done",
            "__attr_mask_shift:",
            "ASL A",
            "DEY",
            "BNE __attr_mask_shift",
            "__attr_mask_done:",
            "EOR #$FF",
            "LDX __at_idx",
            "AND __attr,X",
            "STA __at_val",
            "LDA __at_pal",
            "AND #$03",
            "LDY __at_shift",
            "BEQ __attr_val_done",
            "__attr_val_shift:",
            "ASL A",
            "DEY",
            "BNE __attr_val_shift",
            "__attr_val_done:",
            "ORA __at_val",
            "LDX __at_idx",
            "STA __attr,X",
            "STA __v_data",
            "TXA",
            "AND #$3F",
            "CLC",
            "ADC #$C0",
            "STA __v_lo",
            "LDA __at_idx",
            "AND #$40",
            "BEQ __attr_set_nt0",
            "LDA #$27",
            "JMP __attr_set_addr",
            "__attr_set_nt0:",
            "LDA #$23",
            "__attr_set_addr:",
            "STA __v_hi",
            "JMP __vram_put",
            "",
            "_bg_attr:",
            "LDA __a_bg_attr_cx",
            "STA __at_cx",
            "LDA __a_bg_attr_cy",
            "STA __at_cy",
            "LDA __a_bg_attr_pal",
            "STA __at_pal",
            "JMP __attr_set",
        )

    def _metatile(self) -> None:
        self.emit(
            "",
            # __mt_x/__mt_y = cell coordinates, __mt_id = metatile.
            "__meta_draw:",
            "LDA __mt_x",
            "ASL A",
            "STA __rp2",
            "LDA __mt_y",
            "ASL A",
            "STA __rp2+1",
            "LDX __mt_id",
            "LDA __mt_tl,X",
            "STA __v_data",
            "LDA __rp2",
            "STA __v_x",
            "LDA __rp2+1",
            "STA __v_y",
            "JSR __meta_put",
            "LDX __mt_id",
            "LDA __mt_tr,X",
            "STA __v_data",
            "LDA __rp2",
            "CLC",
            "ADC #$01",
            "STA __v_x",
            "LDA __rp2+1",
            "STA __v_y",
            "JSR __meta_put",
            "LDX __mt_id",
            "LDA __mt_bl,X",
            "STA __v_data",
            "LDA __rp2",
            "STA __v_x",
            "LDA __rp2+1",
            "CLC",
            "ADC #$01",
            "STA __v_y",
            "JSR __meta_put",
            "LDX __mt_id",
            "LDA __mt_br,X",
            "STA __v_data",
            "LDA __rp2",
            "CLC",
            "ADC #$01",
            "STA __v_x",
            "LDA __rp2+1",
            "CLC",
            "ADC #$01",
            "STA __v_y",
            "JSR __meta_put",
            "LDX __mt_id",
            "LDA __mt_pal,X",
            "STA __at_pal",
            "LDA __mt_x",
            "STA __at_cx",
            "LDA __mt_y",
            "STA __at_cy",
            "JMP __attr_set",
            "",
            "__meta_put:",
            "LDA __v_data",
            "PHA",
            "JSR __vram_addr",
            "PLA",
            "STA __v_data",
            "JMP __vram_put",
            "",
            "_bg_meta:",
            "LDA __a_bg_meta_cx",
            "STA __mt_x",
            "LDA __a_bg_meta_cy",
            "STA __mt_y",
            "LDA __a_bg_meta_metatile",
            "STA __mt_id",
            "JMP __meta_draw",
        )

    def _map(self) -> None:
        self.emit(
            "",
            "_bg_map:",
            "LDA __rendering",
            "PHA",
            "LDA #$00",
            "STA $2001",
            "STA __rendering",
            "LDX __a_bg_map_map",
            "LDA __map_lo,X",
            "STA __rp",
            "LDA __map_hi,X",
            "STA __rp+1",
            "LDY #$00",
            "LDA (__rp),Y",
            "STA __mp_w",
            "INY",
            "LDA (__rp),Y",
            "STA __mp_h",
            "LDA #$00",
            "STA __mp_i",
            "STA __mp_cy",
            "__bg_map_row:",
            "LDA __mp_cy",
            "CMP __mp_h",
            "BCS __bg_map_done",
            "LDA #$00",
            "STA __mp_cx",
            "__bg_map_col:",
            "LDA __mp_cx",
            "CMP __mp_w",
            "BCS __bg_map_next",
            "LDY __mp_i",
            "INY",
            "INY",
            "LDA (__rp),Y",
            "STA __mt_id",
            "LDA __mp_cx",
            "STA __mt_x",
            "LDA __mp_cy",
            "STA __mt_y",
            "JSR __meta_draw",
            "INC __mp_i",
            "INC __mp_cx",
            "JMP __bg_map_col",
            "__bg_map_next:",
            "INC __mp_cy",
            "JMP __bg_map_row",
            "__bg_map_done:",
            "PLA",
            "STA __rendering",
            "BEQ __bg_map_off",
            f"LDA #{self.render_mask}",
            "STA $2001",
            "__bg_map_off:",
            "RTS",
        )

    def _font(self) -> None:
        self.emit(
            "",
            "_bg_text:",
            "LDA __a_bg_text_x",
            "STA __v_x",
            "LDA __a_bg_text_y",
            "STA __v_y",
            "LDA __a_bg_text_text",
            "STA __rp",
            "LDA __a_bg_text_text+1",
            "STA __rp+1",
            "LDA __a_bg_text_len",
            "STA __run_len",
            "JMP __bg_run",
            "",
            "_bg_char:",
            "LDA __a_bg_char_x",
            "STA __v_x",
            "LDA __a_bg_char_y",
            "STA __v_y",
            "LDA __a_bg_char_code",
            "SEC",
            "SBC #32",
            "CMP #96",
            "BCC __bg_char_ok",
            "LDA #$00",
            "__bg_char_ok:",
            "TAX",
            "LDA __font_ascii,X",
            "STA __v_data",
            "JSR __vram_addr",
            "JMP __vram_put",
        )

    def _bcd(self) -> None:
        digit0 = self.assets.font_map.get("0", 0)
        self.emit(
            "",
            # Renders a u16 as up to five decimal digits by repeated
            # subtraction of the powers of ten.
            "_bg_number:",
            "LDA __a_bg_number_value",
            "STA __nm_lo",
            "LDA __a_bg_number_value+1",
            "STA __nm_hi",
            "LDA __a_bg_number_digits",
            "BNE __bg_number_go",
            "RTS",
            "__bg_number_go:",
            "CMP #$06",
            "BCC __bg_number_ok",
            "LDA #$05",
            "__bg_number_ok:",
            "STA __nm_n",
            "SEC",
            "SBC #$01",
            "STA __nm_p",
            "LDA #$00",
            "STA __nm_i",
            "__bg_number_digit:",
            "LDX __nm_p",
            "LDA __pow10_lo,X",
            "STA __rp2",
            "LDA __pow10_hi,X",
            "STA __rp2+1",
            "LDA #$00",
            "STA __nm_d",
            "__bg_number_sub:",
            "LDA __nm_lo",
            "SEC",
            "SBC __rp2",
            "TAY",
            "LDA __nm_hi",
            "SBC __rp2+1",
            "BCC __bg_number_store",
            "STA __nm_hi",
            "STY __nm_lo",
            "INC __nm_d",
            "JMP __bg_number_sub",
            "__bg_number_store:",
            "LDX __nm_i",
            "LDA __nm_d",
            "CLC",
            f"ADC #{digit0}",
            "STA __num_buf,X",
            "INC __nm_i",
            "DEC __nm_p",
            "BPL __bg_number_digit",
            "LDA __a_bg_number_x",
            "STA __v_x",
            "LDA __a_bg_number_y",
            "STA __v_y",
            "LDA #<__num_buf",
            "STA __rp",
            "LDA #>__num_buf",
            "STA __rp+1",
            "LDA __nm_n",
            "STA __run_len",
            "JMP __bg_run",
            "",
            "__pow10_lo:",
            ".byte $01, $0A, $64, $E8, $10",
            "__pow10_hi:",
            ".byte $00, $00, $00, $03, $27",
        )

    # -- sprites -----------------------------------------------------------

    def _oam(self) -> None:
        self.emit(
            "",
            "_spr_clear:",
            "LDA #$00",
            "STA __oam_index",
            "LDX #$00",
            "LDA #$F0",
            "__spr_clear_loop:",
            "STA $0200,X",
            "INX",
            "INX",
            "INX",
            "INX",
            "BNE __spr_clear_loop",
            "RTS",
            "",
            "_spr_count:",
            "LDA __oam_index",
            "LSR A",
            "LSR A",
            "RTS",
            "",
            # __sp_x/__sp_y/__sp_t/__sp_a; caller has already checked for room.
            "__spr_add:",
            "LDX __oam_index",
            "LDA __sp_y",
            "SEC",
            "SBC #$01",
            "STA $0200,X",
            "INX",
            "LDA __sp_t",
            "STA $0200,X",
            "INX",
            "LDA __sp_a",
            "STA $0200,X",
            "INX",
            "LDA __sp_x",
            "STA $0200,X",
            "INX",
            "STX __oam_index",
            "RTS",
            "",
            "_spr:",
            "LDA __oam_index",
            "CMP #$FC",
            "BCC __spr_room",
            "RTS",
            "__spr_room:",
            "LDA __a_spr_x",
            "STA __sp_x",
            "LDA __a_spr_y",
            "STA __sp_y",
            "LDA __a_spr_tile",
            "STA __sp_t",
            "LDA __a_spr_attr",
            "STA __sp_a",
            "JMP __spr_add",
        )

    def _metasprite(self) -> None:
        self.emit(
            "",
            "_spr_meta:",
            "LDA __a_spr_meta_x",
            "STA __a_spr_meta_flip_x",
            "LDA __a_spr_meta_y",
            "STA __a_spr_meta_flip_y",
            "LDA __a_spr_meta_metasprite",
            "STA __a_spr_meta_flip_metasprite",
            "LDA #$00",
            "STA __a_spr_meta_flip_flip",
            "JMP _spr_meta_flip",
            "",
            "_spr_meta_flip:",
            "LDX __a_spr_meta_flip_metasprite",
            "LDA __ms_lo,X",
            "STA __rp",
            "LDA __ms_hi,X",
            "STA __rp+1",
            "LDA #$00",
            "STA __ms_i",
            "__spr_meta_loop:",
            "LDY __ms_i",
            "LDA (__rp),Y",
            "CMP #$80",
            "BNE __spr_meta_entry",
            "RTS",
            "__spr_meta_entry:",
            "STA __ms_dx",
            "LDA __oam_index",
            "CMP #$FC",
            "BCC __spr_meta_room",
            "RTS",
            "__spr_meta_room:",
            "LDA __a_spr_meta_flip_flip",
            "BEQ __spr_meta_noflip",
            # Mirroring the group mirrors each cell's offset: a cell is 8 wide,
            # so the mirrored offset is -dx - 8 from the same anchor.
            "LDA #$00",
            "SEC",
            "SBC __ms_dx",
            "SEC",
            "SBC #$08",
            "STA __ms_dx",
            "__spr_meta_noflip:",
            "LDA __a_spr_meta_flip_x",
            "CLC",
            "ADC __ms_dx",
            "STA __sp_x",
            "LDY __ms_i",
            "INY",
            "LDA (__rp),Y",
            "CLC",
            "ADC __a_spr_meta_flip_y",
            "STA __sp_y",
            "INY",
            "LDA (__rp),Y",
            "STA __sp_t",
            "INY",
            "LDA (__rp),Y",
            "STA __sp_a",
            "LDA __a_spr_meta_flip_flip",
            "BEQ __spr_meta_attr_ok",
            "LDA __sp_a",
            "EOR #$40",
            "STA __sp_a",
            "__spr_meta_attr_ok:",
            "JSR __spr_add",
            "LDA __ms_i",
            "CLC",
            "ADC #$04",
            "STA __ms_i",
            "JMP __spr_meta_loop",
        )

    # -- scroll ------------------------------------------------------------

    def _scroll(self) -> None:
        self.emit(
            "",
            "_scroll_set:",
            "LDA __a_scroll_set_x",
            "STA __scroll_x_lo",
            "LDA __a_scroll_set_x+1",
            "STA __scroll_x_hi",
            "LDA __a_scroll_set_y",
            "STA __scroll_y",
            "RTS",
        )

    # -- palette -----------------------------------------------------------

    def _palette(self) -> None:
        self.emit(
            "",
            "_pal_load:",
            "LDX __a_pal_load_palette",
            "LDA __pal_lo,X",
            "STA __rp",
            "LDA __pal_hi,X",
            "STA __rp+1",
            "LDY #$00",
            "__pal_load_loop:",
            "LDA (__rp),Y",
            "STA __pal,Y",
            "INY",
            "CPY #$20",
            "BNE __pal_load_loop",
            "LDA #$01",
            "STA __pal_dirty",
            "RTS",
            "",
            "_pal_set:",
            "LDX __a_pal_set_index",
            "CPX #$20",
            "BCS __pal_set_done",
            "LDA __a_pal_set_color",
            "STA __pal,X",
            "LDA #$01",
            "STA __pal_dirty",
            "__pal_set_done:",
            "RTS",
            "",
            "_pal_bright:",
            "LDA __a_pal_bright_level",
            "CMP #$05",
            "BCC __pal_bright_ok",
            "LDA #$04",
            "__pal_bright_ok:",
            "STA __pal_bright",
            "LDA #$01",
            "STA __pal_dirty",
            "RTS",
            "",
            # Runs inside the NMI; 32 bytes is well inside the vblank budget.
            "__pal_upload:",
            "LDA __pal_dirty",
            "BNE __pal_upload_go",
            "RTS",
            "__pal_upload_go:",
            "LDA #$00",
            "STA __pal_dirty",
            "LDA $2002",
            "LDA #$3F",
            "STA $2006",
            "LDA #$00",
            "STA $2006",
            "LDY #$00",
            "__pal_upload_loop:",
            "LDA __pal,Y",
            "STA __pd_in",
            "STY __pd_t",
            "JSR __pal_dim",
            "STA $2007",
            "LDY __pd_t",
            "INY",
            "CPY #$20",
            "BNE __pal_upload_loop",
            # Leave the VRAM address pointing at $3F00 so the backdrop colour
            # is what shows during the rest of the frame.
            "LDA $2002",
            "LDA #$3F",
            "STA $2006",
            "LDA #$00",
            "STA $2006",
            "RTS",
            "",
            # Drops a colour by (4 - brightness) NES luminance rows.
            "__pal_dim:",
            "LDA #$04",
            "SEC",
            "SBC __pal_bright",
            "BNE __pal_dim_work",
            "LDA __pd_in",
            "RTS",
            "__pal_dim_work:",
            "STA __pd_dim",
            "LDA __pd_in",
            "AND #$0F",
            "CMP #$0E",
            "BCS __pal_dim_black",
            "LDA __pd_in",
            "AND #$30",
            "LSR A",
            "LSR A",
            "LSR A",
            "LSR A",
            "SEC",
            "SBC __pd_dim",
            "BCC __pal_dim_black",
            "ASL A",
            "ASL A",
            "ASL A",
            "ASL A",
            "STA __pd_dim",
            "LDA __pd_in",
            "AND #$0F",
            "ORA __pd_dim",
            "RTS",
            "__pal_dim_black:",
            "LDA #$0F",
            "RTS",
        )

    # -- input -------------------------------------------------------------

    def _pad(self) -> None:
        self.emit(
            "",
            "_pad_poll:",
            "LDA __pad_held",
            "STA __pad_prev",
            "LDA __pad_held+1",
            "STA __pad_prev+1",
            "LDA #$01",
            "STA $4016",
            "LDA #$00",
            "STA $4016",
            "LDX #$08",
            "__pad_poll_loop:",
            "LDA $4016",
            "LSR A",
            "ROL __pad_held",
            "LDA $4017",
            "LSR A",
            "ROL __pad_held+1",
            "DEX",
            "BNE __pad_poll_loop",
            "LDX #$01",
            "__pad_edge_loop:",
            "LDA __pad_held,X",
            "STA __t0",
            "EOR #$FF",
            "AND __pad_prev,X",
            "STA __pad_released,X",
            "LDA __pad_prev,X",
            "EOR #$FF",
            "AND __t0",
            "STA __pad_pressed,X",
            "DEX",
            "BPL __pad_edge_loop",
            "RTS",
            "",
            "_pad_held:",
            "LDX __a_pad_held_player",
            "CPX #$02",
            "BCC __pad_held_ok",
            "LDA #$00",
            "RTS",
            "__pad_held_ok:",
            "LDA __pad_held,X",
            "RTS",
            "",
            "_pad_pressed:",
            "LDX __a_pad_pressed_player",
            "CPX #$02",
            "BCC __pad_pressed_ok",
            "LDA #$00",
            "RTS",
            "__pad_pressed_ok:",
            "LDA __pad_pressed,X",
            "RTS",
            "",
            "_pad_released:",
            "LDX __a_pad_released_player",
            "CPX #$02",
            "BCC __pad_released_ok",
            "LDA #$00",
            "RTS",
            "__pad_released_ok:",
            "LDA __pad_released,X",
            "RTS",
        )

    # -- random ------------------------------------------------------------

    def _rand(self) -> None:
        self.emit(
            "",
            "_rand:",
            "LDA __rng_hi",
            "LSR A",
            "STA __rng_hi",
            "LDA __rng_lo",
            "ROR A",
            "STA __rng_lo",
            "BCC __rand_no_xor",
            "LDA __rng_hi",
            "EOR #$B4",
            "STA __rng_hi",
            "__rand_no_xor:",
            "LDA __rng_lo",
            "EOR __rng_hi",
            "RTS",
            "",
            "_rand_seed:",
            "LDA __a_rand_seed_seed",
            "ORA __a_rand_seed_seed+1",
            "BNE __rand_seed_ok",
            "RTS",
            "__rand_seed_ok:",
            "LDA __a_rand_seed_seed",
            "STA __rng_lo",
            "LDA __a_rand_seed_seed+1",
            "STA __rng_hi",
            "RTS",
        )
        if self.has("div"):
            self.emit(
                "",
                "_rand_range:",
                "LDA __a_rand_range_n",
                "BNE __rand_range_ok",
                "RTS",
                "__rand_range_ok:",
                "STA __t0",
                "JSR _rand",
                "STA __t1",
                "JSR __divmod8",
                "LDA __t2",
                "RTS",
            )

    # -- math --------------------------------------------------------------

    def _math(self) -> None:
        self.emit(
            "",
            # A * __t0 -> A = low, __ah = high.
            "__mul8:",
            "STA __t1",
            "LDA #$00",
            "STA __ah",
            "LDX #$08",
            "__mul8_loop:",
            "LSR __t0",
            "BCC __mul8_skip",
            "CLC",
            "ADC __t1",
            "JMP __mul8_shift",
            "__mul8_skip:",
            "CLC",
            "__mul8_shift:",
            "ROR A",
            "ROR __ah",
            "DEX",
            "BNE __mul8_loop",
            "TAX",
            "LDA __ah",
            "STX __ah",
            "RTS",
            "",
            # A / __t0 -> A = quotient, __t2 = remainder.  Restoring division,
            # so the cost does not depend on the size of the quotient.
            "__divmod8:",
            "LDA __t0",
            "BNE __divmod8_go",
            "LDA #$00",
            "STA __t2",
            "RTS",
            "__divmod8_go:",
            "LDA #$00",
            "STA __t2",
            "LDX #$08",
            "__divmod8_loop:",
            "ASL __t1",
            "ROL __t2",
            "LDA __t2",
            "CMP __t0",
            "BCC __divmod8_next",
            "SBC __t0",
            "STA __t2",
            "INC __t1",
            "__divmod8_next:",
            "DEX",
            "BNE __divmod8_loop",
            "LDA __t1",
            "RTS",
            "",
            # {A,__ah} * {__rl,__rh} -> {A,__ah}, low 16 bits.
            "__mul16x16:",
            "STA __t0",
            "LDA __ah",
            "STA __t1",
            "LDA #$00",
            "STA __t2",
            "STA __t3",
            "LDX #$10",
            "__mul16_loop:",
            "LSR __rh",
            "ROR __rl",
            "BCC __mul16_skip",
            "LDA __t2",
            "CLC",
            "ADC __t0",
            "STA __t2",
            "LDA __t3",
            "ADC __t1",
            "STA __t3",
            "__mul16_skip:",
            "ASL __t0",
            "ROL __t1",
            "DEX",
            "BNE __mul16_loop",
            "LDA __t3",
            "STA __ah",
            "LDA __t2",
            "RTS",
            "",
            # {A,__ah} / {__rl,__rh} -> quotient in {A,__ah},
            # remainder in {__t2,__t3}.  Restoring division; the divisor must
            # be 32767 or less, which every practical game divisor is.
            "__div16:",
            "STA __t0",
            "LDA __ah",
            "STA __t1",
            "LDA #$00",
            "STA __t2",
            "STA __t3",
            "LDA __rl",
            "ORA __rh",
            "BNE __div16_go",
            "STA __t0",
            "STA __t1",
            "STA __ah",
            "LDA #$00",
            "RTS",
            "__div16_go:",
            "LDX #$10",
            "__div16_loop:",
            "ASL __t0",
            "ROL __t1",
            "ROL __t2",
            "ROL __t3",
            "LDA __t2",
            "SEC",
            "SBC __rl",
            "TAY",
            "LDA __t3",
            "SBC __rh",
            "BCC __div16_next",
            "STA __t3",
            "STY __t2",
            "INC __t0",
            "__div16_next:",
            "DEX",
            "BNE __div16_loop",
            "LDA __t1",
            "STA __ah",
            "LDA __t0",
            "RTS",
            "",
            "_abs8:",
            "LDA __a_abs8_value",
            "BPL __abs8_done",
            "EOR #$FF",
            "CLC",
            "ADC #$01",
            "__abs8_done:",
            "RTS",
            "",
            "_min8:",
            "LDA __a_min8_a",
            "CMP __a_min8_b",
            "BCC __min8_done",
            "LDA __a_min8_b",
            "__min8_done:",
            "RTS",
            "",
            "_max8:",
            "LDA __a_max8_a",
            "CMP __a_max8_b",
            "BCS __max8_done",
            "LDA __a_max8_b",
            "__max8_done:",
            "RTS",
        )
        if self.has("mul"):
            self.emit(
                "",
                "_mul8:",
                "LDA __a_mul8_b",
                "STA __t0",
                "LDA __a_mul8_a",
                "JMP __mul8",
                "",
                "_mul16:",
                "LDA __a_mul16_b",
                "STA __t0",
                "LDA __a_mul16_a",
                "JMP __mul8",
            )
        if self.has("div"):
            self.emit(
                "",
                "_div8:",
                "LDA __a_div8_b",
                "STA __t0",
                "LDA __a_div8_a",
                "STA __t1",
                "JMP __divmod8",
                "",
                "_mod8:",
                "LDA __a_mod8_b",
                "STA __t0",
                "LDA __a_mod8_a",
                "STA __t1",
                "JSR __divmod8",
                "LDA __t2",
                "RTS",
            )

    def _collision(self) -> None:
        self.emit(
            "",
            # Two boxes overlap when the gap on each axis is smaller than the
            # size of whichever box is on the left/top.
            "_box_hit:",
            "LDA __a_box_hit_ax",
            "CMP __a_box_hit_bx",
            "BCS __box_hit_x_swap",
            "LDA __a_box_hit_bx",
            "SEC",
            "SBC __a_box_hit_ax",
            "CMP __a_box_hit_aw",
            "BCS __box_hit_miss",
            "JMP __box_hit_y",
            "__box_hit_x_swap:",
            "LDA __a_box_hit_ax",
            "SEC",
            "SBC __a_box_hit_bx",
            "CMP __a_box_hit_bw",
            "BCS __box_hit_miss",
            "__box_hit_y:",
            "LDA __a_box_hit_ay",
            "CMP __a_box_hit_by",
            "BCS __box_hit_y_swap",
            "LDA __a_box_hit_by",
            "SEC",
            "SBC __a_box_hit_ay",
            "CMP __a_box_hit_ah",
            "BCS __box_hit_miss",
            "LDA #$01",
            "RTS",
            "__box_hit_y_swap:",
            "LDA __a_box_hit_ay",
            "SEC",
            "SBC __a_box_hit_by",
            "CMP __a_box_hit_bh",
            "BCS __box_hit_miss",
            "LDA #$01",
            "RTS",
            "__box_hit_miss:",
            "LDA #$00",
            "RTS",
        )

    # -- sound -------------------------------------------------------------

    def _sfx(self) -> None:
        self.emit(
            "",
            "_sfx_play:",
            "LDX __a_sfx_play_sfx",
            "LDA __sfx_len,X",
            "BNE __sfx_play_ok",
            "RTS",
            "__sfx_play_ok:",
            "STA __sfx_left",
            "LDA __sfx_start,X",
            "STA __sfx_pos",
            "RTS",
            "",
            "__sfx_tick:",
            "LDA __sfx_left",
            "BNE __sfx_tick_go",
            "RTS",
            "__sfx_tick_go:",
            "LDX __sfx_pos",
            "LDA __sfx_vol,X",
            "ORA #$30",
            "STA $4004",
            "LDA __sfx_note,X",
            "ASL A",
            "TAY",
            "LDA __note_lo,Y",
            "STA $4006",
            "LDA __note_hi,Y",
            "ORA #$08",
            "STA $4007",
            "INC __sfx_pos",
            "DEC __sfx_left",
            "BNE __sfx_tick_done",
            "LDA #$30",
            "STA $4004",
            "__sfx_tick_done:",
            "RTS",
        )

    def _music(self) -> None:
        self.emit(
            "",
            "_music_play:",
            "LDX __a_music_play_song",
            "LDA __song_lo,X",
            "STA __rp",
            "LDA __song_hi,X",
            "STA __rp+1",
            "LDY #$00",
            "LDA (__rp),Y",
            "STA __mus_speed",
            "INY",
            "LDA (__rp),Y",
            "STA __mus_rows_lo",
            "STA __mus_left_lo",
            "INY",
            "LDA (__rp),Y",
            "STA __mus_rows_hi",
            "STA __mus_left_hi",
            "LDA __rp",
            "CLC",
            "ADC #$03",
            "STA __mus_ptr",
            "STA __mus_base_lo",
            "LDA __rp+1",
            "ADC #$00",
            "STA __mus_ptr+1",
            "STA __mus_base_hi",
            "LDA #$01",
            "STA __mus_timer",
            "STA __mus_playing",
            "LDA #$0F",
            "STA $4015",
            "RTS",
            "",
            "_music_stop:",
            "LDA #$00",
            "STA __mus_playing",
            "STA __mus_base_lo",
            "STA __mus_base_hi",
            "JMP __music_silence",
            "",
            "_music_pause:",
            "LDA #$00",
            "STA __mus_playing",
            "JMP __music_silence",
            "",
            "__music_silence:",
            "LDA #$30",
            "STA $4000",
            "STA $4004",
            "STA $400C",
            "LDA #$00",
            "STA $4008",
            "RTS",
            "",
            "_music_resume:",
            "LDA __mus_base_lo",
            "ORA __mus_base_hi",
            "BNE __music_resume_ok",
            "RTS",
            "__music_resume_ok:",
            "LDA #$01",
            "STA __mus_timer",
            "STA __mus_playing",
            "RTS",
            "",
            "__music_tick:",
            "LDA __mus_playing",
            "BNE __music_tick_go",
            "RTS",
            "__music_tick_go:",
            "DEC __mus_timer",
            "BEQ __music_row",
            "RTS",
            "__music_row:",
            "LDA __mus_speed",
            "STA __mus_timer",
            "JSR __music_apply",
            "LDA __mus_ptr",
            "CLC",
            "ADC #$04",
            "STA __mus_ptr",
            "LDA __mus_ptr+1",
            "ADC #$00",
            "STA __mus_ptr+1",
            # 16-bit decrement of the remaining row count, looping at zero.
            "LDA __mus_left_lo",
            "BNE __music_dec_lo",
            "LDA __mus_left_hi",
            "BEQ __music_loop",
            "DEC __mus_left_hi",
            "__music_dec_lo:",
            "DEC __mus_left_lo",
            "LDA __mus_left_lo",
            "ORA __mus_left_hi",
            "BEQ __music_loop",
            "RTS",
            "__music_loop:",
            "LDA __mus_base_lo",
            "STA __mus_ptr",
            "LDA __mus_base_hi",
            "STA __mus_ptr+1",
            "LDA __mus_rows_lo",
            "STA __mus_left_lo",
            "LDA __mus_rows_hi",
            "STA __mus_left_hi",
            "RTS",
            "",
            "__music_apply:",
            # pulse 1
            "LDY #$00",
            "LDA (__mus_ptr),Y",
            "CMP #$01",
            "BEQ __music_p2",
            "TAY",
            "BNE __music_p1_note",
            "LDA #$30",
            "STA $4000",
            "JMP __music_p2",
            "__music_p1_note:",
            "LDA #$B8",
            "STA $4000",
            "TYA",
            "ASL A",
            "TAY",
            "LDA __note_lo,Y",
            "STA $4002",
            "LDA __note_hi,Y",
            "ORA #$08",
            "STA $4003",
            "__music_p2:",
        )
        if self.has("sfx"):
            # A sound effect owns pulse 2 while it plays; the song picks the
            # channel back up on its next row.
            self.emit("LDA __sfx_left", "BEQ __music_p2_free", "JMP __music_tri", "__music_p2_free:")
        self.emit(
            "LDY #$01",
            "LDA (__mus_ptr),Y",
            "CMP #$01",
            "BEQ __music_tri",
            "TAY",
            "BNE __music_p2_note",
            "LDA #$30",
            "STA $4004",
            "JMP __music_tri",
            "__music_p2_note:",
            "LDA #$76",
            "STA $4004",
            "TYA",
            "ASL A",
            "TAY",
            "LDA __note_lo,Y",
            "STA $4006",
            "LDA __note_hi,Y",
            "ORA #$08",
            "STA $4007",
            "__music_tri:",
            "LDY #$02",
            "LDA (__mus_ptr),Y",
            "CMP #$01",
            "BEQ __music_noise",
            "TAY",
            "BNE __music_tri_note",
            "LDA #$00",
            "STA $4008",
            "JMP __music_noise",
            "__music_tri_note:",
            "LDA #$FF",
            "STA $4008",
            "TYA",
            "ASL A",
            "TAY",
            "LDA __note_lo,Y",
            "STA $400A",
            "LDA __note_hi,Y",
            "ORA #$08",
            "STA $400B",
            # noise: 0 rest, 1 hold, 2..15 timbre
            "__music_noise:",
            "LDY #$03",
            "LDA (__mus_ptr),Y",
            "CMP #$01",
            "BEQ __music_apply_done",
            "TAY",
            "BNE __music_noise_hit",
            "LDA #$30",
            "STA $400C",
            "RTS",
            "__music_noise_hit:",
            "LDA #$38",
            "STA $400C",
            "TYA",
            "SEC",
            "SBC #$02",
            "AND #$0F",
            "STA $400E",
            "LDA #$08",
            "STA $400F",
            "__music_apply_done:",
            "RTS",
        )

    # ------------------------------------------------------------------
    # Data tables
    # ------------------------------------------------------------------

    def data_tables(self) -> List[str]:
        out: List[str] = []
        a = self.assets

        def emit_bytes(label: str, values: Sequence[int]) -> None:
            out.append(f"{label}:")
            values = list(values) or [0]
            for i in range(0, len(values), 16):
                chunk = values[i : i + 16]
                out.append(".byte " + ", ".join(f"${v & 0xFF:02X}" for v in chunk))

        def emit_addr_table(label: str, prefix: str, count: int) -> None:
            names = [f"{prefix}{i}" for i in range(count)] or []
            out.append(f"{label}_lo:")
            out.append(".byte " + (", ".join(f"<{n}" for n in names) if names else "$00"))
            out.append(f"{label}_hi:")
            out.append(".byte " + (", ".join(f">{n}" for n in names) if names else "$00"))

        if self.has("font"):
            # ASCII 32..127 -> CHR tile, so bg_char() can print a computed
            # character without the program knowing where the font landed.
            out.append("")
            table = []
            for code in range(32, 128):
                ch = chr(code).upper()
                table.append(a.font_map.get(ch, a.font_map.get(" ", 0)))
            emit_bytes("__font_ascii", table)

        if self.has("notes"):
            out.append("")
            emit_bytes("__note_lo", [p & 0xFF for p in NOTE_PERIODS])
            emit_bytes("__note_hi", [(p >> 8) & 0xFF for p in NOTE_PERIODS])

        if self.has("palette"):
            out.append("")
            for i, values in enumerate(a.palettes):
                emit_bytes(f"__pal_data{i}", values)
            emit_addr_table("__pal", "__pal_data", len(a.palettes))

        if self.has("metasprite"):
            out.append("")
            for i, data in enumerate(a.metasprites):
                emit_bytes(f"__ms_data{i}", data)
            emit_addr_table("__ms", "__ms_data", len(a.metasprites))

        if self.has("metatile"):
            out.append("")
            mts = a.metatiles or [(0, 0, 0, 0, 0)]
            emit_bytes("__mt_tl", [m[0] for m in mts])
            emit_bytes("__mt_tr", [m[1] for m in mts])
            emit_bytes("__mt_bl", [m[2] for m in mts])
            emit_bytes("__mt_br", [m[3] for m in mts])
            emit_bytes("__mt_pal", [m[4] for m in mts])

        if self.has("map"):
            out.append("")
            for i, (w, h, cells) in enumerate(a.maps):
                emit_bytes(f"__map_data{i}", [w, h] + cells)
            emit_addr_table("__map", "__map_data", len(a.maps))

        if self.has("sfx"):
            out.append("")
            starts: List[int] = []
            lengths: List[int] = []
            vols: List[int] = []
            notes: List[int] = []
            for frames in a.sfx:
                starts.append(len(vols))
                lengths.append(len(frames))
                for vol, note in frames:
                    vols.append(vol)
                    notes.append(note)
            emit_bytes("__sfx_start", starts)
            emit_bytes("__sfx_len", lengths)
            emit_bytes("__sfx_vol", vols)
            emit_bytes("__sfx_note", notes)

        if self.has("music"):
            out.append("")
            for i, (speed, rows) in enumerate(a.songs):
                payload = [speed, len(rows) & 0xFF, (len(rows) >> 8) & 0xFF]
                for row in rows:
                    payload.extend(row)
                emit_bytes(f"__song_data{i}", payload)
            emit_addr_table("__song", "__song_data", len(a.songs))
        return out
