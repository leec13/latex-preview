"""Compilation avec TeX Live et analyse du journal."""

from __future__ import annotations

import glob
import html
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from .document import BuiltDocument

ENGINES = ("pdflatex", "lualatex", "xelatex")

# Emplacements courants de TeX Live / MacTeX : une application lancée depuis
# le Finder ou le Dock n'hérite pas toujours du PATH du terminal.
_EXTRA_DIRS = [
    "/Library/TeX/texbin",
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/texbin",
    "/usr/bin",
]

_JOB = "preview"
_FILE_LINE_RE = re.compile(r"^(?:\./)?" + _JOB + r"\.tex:(\d+):\s*(.*)$")
_BANG_RE = re.compile(r"^!\s*(.*)$")
_CONTEXT_RE = re.compile(r"^l\.(\d+)\s?(.*)$")
_LAST_CS_RE = re.compile(r"(\\[A-Za-z@]+|\\.)\s*$")


def find_engine(engine: str) -> str | None:
    """Chemin absolu de l'exécutable TeX, ou None s'il est introuvable."""
    found = shutil.which(engine)
    if found:
        return found
    dirs = list(_EXTRA_DIRS)
    dirs += sorted(glob.glob("/usr/local/texlive/*/bin/*"), reverse=True)
    for d in dirs:
        p = os.path.join(d, engine)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


# Messages TeX fréquents, traduits et expliqués.
_FRIENDLY = [
    ("Undefined control sequence", "Commande inconnue (faute de frappe, ou package/macro manquant dans le préambule)"),
    ("Missing $ inserted", "Symbole mathématique hors du mode math, ou ligne vide dans une équation"),
    ("Missing } inserted", "Accolade fermante « } » manquante"),
    ("Extra }, or forgotten", "Accolade « } » en trop"),
    ("Missing { inserted", "Accolade ouvrante « { » manquante"),
    ("Extra alignment tab", "Trop de « & » sur une ligne (colonnes de matrice ou d'alignement)"),
    ("Misplaced alignment tab", "« & » utilisé hors d'un environnement d'alignement"),
    ("Missing \\right. inserted", "\\left sans \\right correspondant"),
    ("Extra \\right", "\\right sans \\left correspondant"),
    ("Double superscript", "Double exposant : utilisez des accolades, ex. {x^a}^b"),
    ("Double subscript", "Double indice : utilisez des accolades, ex. {x_i}_j"),
    ("Environment", "Environnement inconnu"),
    ("not found", "Fichier ou package introuvable"),
    ("Display math should end with $$", "Les $$ ne sont pas appariés"),
    ("File ended while scanning", "Fin du texte atteinte avant la fermeture d'un argument (accolade manquante ?)"),
    ("Runaway argument", "Argument non terminé (accolade manquante ?)"),
]


@dataclass
class TexError:
    message: str
    zone: str | None = None   # "extrait", "préambule" ou None
    line: int | None = None   # numéro de ligne dans la zone
    context: str = ""         # extrait de la ligne fautive (l.12 ...)

    @property
    def friendly(self) -> str:
        """Message en français si connu, sinon le message TeX d'origine."""
        for key, fr in _FRIENDLY:
            if key in self.message:
                return f"{fr} — <i>{html.escape(self.message)}</i>"
        return self.message

    def describe(self) -> str:
        where = ""
        if self.line is not None:
            where = f"ligne {self.line}" + (" du préambule" if self.zone == "préambule" else "")
            where += " : "
        ctx = f"  ⟶  {self.context}" if self.context else ""
        return f"{where}{self.message}{ctx}"


@dataclass
class CompileResult:
    ok: bool
    pdf_bytes: bytes | None
    log: str
    errors: list[TexError] = field(default_factory=list)
    duration: float = 0.0


class TexCompiler:
    """Compile dans un dossier temporaire réutilisé (une compilation à la fois)."""

    def __init__(self) -> None:
        self._dir = Path(tempfile.mkdtemp(prefix="latex_preview_"))

    def cleanup(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)

    def compile(self, doc: BuiltDocument, engine: str = "pdflatex", timeout: float = 30.0) -> CompileResult:
        exe = find_engine(engine)
        if exe is None:
            msg = (f"Exécutable « {engine} » introuvable. Vérifiez que TeX Live / MacTeX "
                   "est installé (sur macOS : /Library/TeX/texbin).")
            return CompileResult(False, None, msg, [TexError(msg)])

        self._dir.mkdir(parents=True, exist_ok=True)
        tex = self._dir / f"{_JOB}.tex"
        pdf = self._dir / f"{_JOB}.pdf"
        logf = self._dir / f"{_JOB}.log"
        for p in (pdf, logf):
            p.unlink(missing_ok=True)
        tex.write_text(doc.source, encoding="utf-8")

        cmd = [exe, "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
               "-no-shell-escape", tex.name]
        env = dict(os.environ)
        env["PATH"] = os.path.dirname(exe) + os.pathsep + env.get("PATH", "")
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(cmd, cwd=self._dir, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=timeout, env=env)
            out = proc.stdout.decode("utf-8", "replace")
            code = proc.returncode
        except OSError as exc:  # dossier supprimé pendant la fermeture, etc.
            msg = f"Impossible de lancer {engine} : {exc}"
            return CompileResult(False, None, msg, [TexError(msg)])
        except subprocess.TimeoutExpired:
            msg = f"Compilation interrompue après {timeout:.0f} s."
            return CompileResult(False, None, msg, [TexError(msg)], time.perf_counter() - t0)
        duration = time.perf_counter() - t0

        log = logf.read_text("utf-8", "replace") if logf.exists() else out
        errors = parse_errors(log, doc)
        if code == 0 and pdf.exists():
            return CompileResult(True, pdf.read_bytes(), log, [], duration)
        if not errors:
            errors = [TexError("La compilation a échoué (voir le journal).")]
        return CompileResult(False, None, log, errors, duration)


def parse_errors(log: str, doc: BuiltDocument) -> list[TexError]:
    errors: list[TexError] = []
    lines = log.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _FILE_LINE_RE.match(line)
        b = _BANG_RE.match(line) if not m else None
        if m or b:
            message = (m.group(2) if m else b.group(1)).strip()
            if message.startswith("==>") or message.startswith("Emergency stop"):
                i += 1
                continue
            tex_line = int(m.group(1)) if m else None
            context = ""
            first_ctx = None
            # Le contexte « l.<n> ... » suit quelques lignes plus bas ; la
            # première ligne de contexte se termine par le symbole fautif.
            for j in range(i + 1, min(i + 12, len(lines))):
                c = _CONTEXT_RE.match(lines[j])
                if c:
                    tex_line = tex_line or int(c.group(1))
                    context = c.group(2).strip()
                    if first_ctx is None:
                        first_ctx = context
                    break
                if first_ctx is None and lines[j].strip():
                    first_ctx = lines[j]
            err = TexError(message, context=context)
            if tex_line is not None:
                mapped = doc.map_line(tex_line)
                if mapped:
                    err.zone, err.line = mapped
            # amsmath signale les erreurs sur \end{...} : on retrouve la
            # commande inconnue directement dans l'extrait.
            if "Undefined control sequence" in message and first_ctx:
                cs = _LAST_CS_RE.search(first_ctx.rstrip())
                if cs:
                    found = doc.find_token_line(cs.group(1))
                    if found is not None and doc.mode != "full":
                        err.zone, err.line = "extrait", found
                    err.context = cs.group(1)
            if err.zone == "extrait" and err.line and doc.mode != "full":
                err.line = min(err.line, doc.user_line_count())
            errors.append(err)
        i += 1
    # Dédoublonnage en gardant l'ordre.
    seen, unique = set(), []
    for e in errors:
        key = (e.message, e.line)
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique
