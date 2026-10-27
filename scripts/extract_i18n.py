#!/usr/bin/python3
"""Extrai os textos de interface (IDs de mensagem, em português) do código por AST e compara com os catálogos.

uso: scripts/extract_i18n.py            -> lista candidatos que ainda não estão em data/i18n/_msgids.json
     scripts/extract_i18n.py --write    -> grava a lista candidata em data/i18n/_candidates.json
O arquivo _msgids.json é a fonte da verdade (revisada à mão); os testes exigem que todo ID exista em todos os idiomas."""
import ast
import glob
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "captura", "data", "i18n")

PT = re.compile(r"[À-ÿ]|\b(de|da|do|para|com|em|as|os|uma?|que|não|Abrir|Copiar|Salvar|Fechar|Ativado|Desativado|tela|captura|texto|janela|imagem|arquivo|pasta)\b", re.I)
# textos que parecem mensagens mas não são interface (nomes de pasta, comandos, fontes, mensagens de log, fragmentos já migrados)
NOT_UI = {"Capturas de Tela", "Gravações de Tela", "captura --snip", "Noto Color Emoji ", "Selawik ", "atalho global não configurado:",
          "falha ao salvar automaticamente:", "notificação indisponível:", "falha ao configurar a tecla Imprimir tela:",
          "ToolFlyout supports pen and hl; shapes use shape_bar.ShapeConfig"}
IGNORE_WORDS = {"Pango", "Gtk", "Gdk", "Wnck", "Sans", "Selawik", "Semibold", "Print", "Notify", "Pinta", "Krita", "Drawing", "Noto Color Emoji",
                "PNG", "JPEG", "BMP", "Emoji"}


# pedaços de mensagens que agora são IDs completos com {campos} (ver i18n.trf)
FRAGMENTS = {"A cor ", " foi copiada para a área de transferência.", "Salvo em ", "Editar no ", "\nSelecione para marcar e compartilhar.",
             "\nSelecione para abrir.", "Ferramenta de Captura ", "\n\nO arquivo foi mantido em:\n", "Não foi possível capturar a tela: ",
             "Ferramenta de Captura (Imprimir tela)"}


def docstrings(tree):
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(getattr(n.body[0], "value", None), ast.Constant):
            ids.add(id(n.body[0].value))
    return ids


def candidates():
    out = {}
    FR = FRAGMENTS
    for f in sorted(glob.glob(os.path.join(ROOT, "captura", "*.py"))):
        if f.endswith(("i18n.py", "theme.py", "icons.py")):
            continue
        tree = ast.parse(open(f, encoding="utf-8").read())
        ds = docstrings(tree)
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)) or id(n) in ds:
                continue
            s = n.value
            if s in FR or s in IGNORE_WORDS or s in NOT_UI or s.startswith("ToolFlyout") or len(s) < 3 or not re.search(r"[A-Za-zÀ-ÿ]", s):
                continue
            if s.startswith(("#", ".", "org.", "/", "http", "<", "rgba", "ic_", "~", "-")) or "%" in s and "(" not in s:
                continue
            if re.fullmatch(r"[a-z0-9_.\-/:#%@\[\]{}() ,+*]+", s) and " " not in s:
                continue
            if (" " in s and re.search(r"[A-ZÀ-Ý]", s[:1])) or PT.search(s) or re.fullmatch(r"[A-ZÀ-Ý][a-zà-ÿ]{2,}", s):
                out.setdefault(s, []).append("%s:%d" % (os.path.basename(f), n.lineno))
    return out


if __name__ == "__main__":
    cand = {k: v for k, v in candidates().items() if k not in FRAGMENTS}
    path = os.path.join(DATA, "_msgids.json")
    have = set(json.load(open(path, encoding="utf-8"))) if os.path.exists(path) else set()
    if "--write" in sys.argv:
        json.dump({k: v[:3] for k, v in cand.items()}, open(os.path.join(DATA, "_candidates.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    new = {k: v for k, v in cand.items() if k not in have}
    print("%d candidatos, %d já catalogados, %d novos" % (len(cand), len(cand) - len(new), len(new)))
    for k, v in new.items():
        print("  %-60r %s" % (k[:60], v[0]))
