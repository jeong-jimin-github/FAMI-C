"""FAMI-C: an LLM-first C compiler and ROM builder for the NES/Famicom."""

from .compiler import BuildResult, build_file, compile_source  # noqa: F401
from .diagnostics import CompileError, Diagnostic  # noqa: F401

__version__ = "2.0.0"
