"""
pdf_report.py — Relatório em PDF de todas as abas do TestingStudio Web.

Duas partes independentes do Streamlit:

1. Registrador: um "proxy" de `st` que repassa tudo ao Streamlit e, ao mesmo tempo, anota o que
   é exibido (títulos, textos, tabelas, métricas, avisos, código e o grafo). A tela não muda.
2. build_pdf(): transforma o que foi anotado em um PDF A4 com índice, tabelas que quebram
   linha (nada é cortado), o grafo de fluxo de controle e o gráfico de fronteira desenhados
   como vetores.
"""
from __future__ import annotations

import datetime
import html
import io
import re
import textwrap
from collections import OrderedDict
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (BaseDocTemplate, Flowable, Frame, KeepTogether, PageBreak, PageTemplate,
                                Paragraph, Preformatted, Spacer, Table, TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents

# ===========================================================================
# 1. Registrador (proxy do módulo streamlit)
# ===========================================================================
_SKIP_MD = ("<style", 'class="ts-head"')


class _Ctx:
    """Contêiner (aba, expansor, coluna) que registra um marcador ao ser aberto."""

    def __init__(self, real, blocos, marcador=None):
        self._real, self._blocos, self._marcador = real, blocos, marcador

    def __enter__(self):
        if self._marcador:
            self._blocos.append(self._marcador)
        return self._real.__enter__()

    def __exit__(self, *a):
        return self._real.__exit__(*a)

    def __getattr__(self, nome):
        return getattr(self._real, nome)


class _Coluna(_Ctx):
    def metric(self, label, value, delta=None, *a, **k):
        self._blocos.append(("metric", str(label), str(value), None if delta is None else str(delta)))
        return self._real.metric(label, value, delta, *a, **k)


class Registrador:
    """Use: `st = Registrador(streamlit)`. Tudo que não é registrado passa direto ao Streamlit."""

    def __init__(self, real):
        object.__setattr__(self, "_real", real)
        object.__setattr__(self, "blocos", [])
        object.__setattr__(self, "_n_tabs", 0)

    def __getattr__(self, nome):
        attr = getattr(self._real, nome)
        wrap = getattr(Registrador, "_w_" + nome, None)
        return wrap(self, attr) if wrap else attr

    # -- conteúdo exibido -----------------------------------------------------
    def _w_markdown(self, f):
        def g(body, *a, **k):
            t = str(body)
            if not any(s in t for s in _SKIP_MD):
                self.blocos.append(("md", t))
            return f(body, *a, **k)
        return g

    def _w_caption(self, f):
        def g(body, *a, **k):
            self.blocos.append(("cap", str(body)))
            return f(body, *a, **k)
        return g

    def _w_subheader(self, f):
        def g(body, *a, **k):
            self.blocos.append(("h", 2, str(body)))
            return f(body, *a, **k)
        return g

    def _w_dataframe(self, f):
        def g(data, *a, **k):
            try:
                self.blocos.append(("df", pd.DataFrame(data).copy(), bool(k.get("hide_index"))))
            except Exception:                                              # noqa: BLE001
                pass
            return f(data, *a, **k)
        return g

    def _w_code(self, f):
        def g(body, *a, **k):
            self.blocos.append(("code", str(body)))
            return f(body, *a, **k)
        return g

    def _w_graphviz_chart(self, f):
        def g(figure_or_dot, *a, **k):
            if isinstance(figure_or_dot, str):
                self.blocos.append(("dot", figure_or_dot))
            return f(figure_or_dot, *a, **k)
        return g

    # -- contêineres ------------------------------------------------------------
    def _w_columns(self, f):
        def g(*a, **k):
            return [_Coluna(c, self.blocos) for c in f(*a, **k)]
        return g

    def _w_expander(self, f):
        def g(label, *a, **k):
            return _Ctx(f(label, *a, **k), self.blocos, ("exp", str(label)))
        return g

    def _w_tabs(self, f):
        def g(labels, *a, **k):
            object.__setattr__(self, "_n_tabs", self._n_tabs + 1)
            nivel = 1 if self._n_tabs == 1 else 2
            return [_Ctx(t, self.blocos, ("tab", nivel, str(l))) for t, l in zip(f(labels, *a, **k), labels)]
        return g

    # -- registro explícito (dados que o app não exibe com st.dataframe/markdown) ---
    def registrar(self, tipo, *dados):
        self.blocos.append((tipo, *dados))


# ===========================================================================
# 2. Fontes e limpeza de texto
# ===========================================================================
_FONTE = {}
_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2705\u274C\u2796\u26A0\u2B07\u2B06\uFE0F\u200d]")
_TROCAS = {"ε": "e", "→": "->", "−": "-", "×": "x", "÷": "/", "≥": ">=", "≤": "<=", "≠": "!=", "⊇": ">=",
           "●": "*", "·": "-", "…": "...", "✔": "v", "“": '"', "”": '"', "‘": "'", "’": "'", "–": "-",
           "—": "-", "◇": "<>", "▭": "[]", "⇒": "=>", "↑": "^", "²": "2", "⁻": "-", "Σ": "S", "↺": ""}


def _registrar_fontes():
    if _FONTE:
        return _FONTE
    pastas = [Path(__file__).parent / "fonts", Path("/usr/share/fonts/truetype/dejavu"),
              Path("/usr/share/fonts/dejavu"), Path("/usr/share/fonts/TTF")]
    try:
        import matplotlib
        pastas.append(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:                                                      # noqa: BLE001
        pass
    for p in pastas:
        if (p / "DejaVuSans.ttf").exists() and (p / "DejaVuSans-Bold.ttf").exists():
            def reg(nome, arq, padrao):
                f = p / arq
                pdfmetrics.registerFont(TTFont(nome, str(f if f.exists() else p / padrao)))
            reg("DJ", "DejaVuSans.ttf", "DejaVuSans.ttf")
            reg("DJ-B", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf")
            reg("DJ-I", "DejaVuSans-Oblique.ttf", "DejaVuSans.ttf")
            reg("DJ-BI", "DejaVuSans-BoldOblique.ttf", "DejaVuSans-Bold.ttf")
            reg("DJ-M", "DejaVuSansMono.ttf", "DejaVuSans.ttf")
            reg("DJ-MB", "DejaVuSansMono-Bold.ttf", "DejaVuSansMono.ttf")
            pdfmetrics.registerFontFamily("DJ", normal="DJ", bold="DJ-B", italic="DJ-I", boldItalic="DJ-BI")
            _FONTE.update(sans="DJ", bold="DJ-B", mono="DJ-M", monob="DJ-MB", unicode=True)
            return _FONTE
    _FONTE.update(sans="Helvetica", bold="Helvetica-Bold", mono="Courier", monob="Courier-Bold", unicode=False)
    return _FONTE


def limpar(t) -> str:
    """Remove emojis; sem fonte Unicode, troca símbolos por equivalentes em ASCII."""
    t = _EMOJI.sub("", "" if t is None else str(t))
    if not _FONTE.get("unicode", True):
        for a, b in _TROCAS.items():
            t = t.replace(a, b)
        t = t.encode("latin-1", "replace").decode("latin-1")
    return t.strip()


def _esc(t) -> str:
    return html.escape(limpar(t), quote=False)


def _md_inline(t) -> str:
    t = _esc(t)
    t = re.sub(r"`([^`]+)`", r'<font face="MONO">\1</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<i>\1</i>", t)
    return t.replace('face="MONO"', f'face="{_FONTE["mono"]}"')


def _html_inline(t) -> str:
    t = str(t).replace("<br>", "<br/>").replace("<code>", '<font face="MONO">').replace("</code>", "</font>")
    t = re.sub(r"</?(?!b>|i>|sup>|sub>|br/>|font)[a-zA-Z][^>]*>", "", t)
    return limpar(t).replace('face="MONO"', f'face="{_FONTE["mono"]}"')


# ===========================================================================
# 3. Estilos
# ===========================================================================
INK, MUTED, LINE = colors.HexColor("#1B1B26"), colors.HexColor("#6B6B80"), colors.HexColor("#CFCBE0")
ACCENT, HEAD_BG, ZEBRA = colors.HexColor("#D9480F"), colors.HexColor("#ECE8F6"), colors.HexColor("#F8F7FC")
NOTAS = {"": ("#E3F4EC", "#0B7A4F"), "warn": ("#FBF0DB", "#8F5600"), "bad": ("#FBE7EC", "#C0183F"),
         "info": ("#E6EEFB", "#2253B8")}
LARGURA = A4[0] - 2 * 36


def _estilos():
    f = _registrar_fontes()
    base = dict(fontName=f["sans"], textColor=INK, leading=12.4, fontSize=8.8)
    return {
        "p": ParagraphStyle("p", spaceAfter=4, **base),
        "cap": ParagraphStyle("cap", spaceAfter=4, **{**base, "fontSize": 7.8, "leading": 10.6, "textColor": MUTED}),
        "h1": ParagraphStyle("H1", fontName=f["bold"], fontSize=17, leading=21, textColor=INK, spaceBefore=0, spaceAfter=8, keepWithNext=1),
        "h2": ParagraphStyle("H2", fontName=f["bold"], fontSize=12.5, leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=5, keepWithNext=1),
        "h3": ParagraphStyle("h3", fontName=f["bold"], fontSize=10.4, leading=13.5, textColor=INK, spaceBefore=8, spaceAfter=3, keepWithNext=1),
        "h4": ParagraphStyle("h4", fontName=f["bold"], fontSize=9.4, leading=12.5, textColor=INK, spaceBefore=6, spaceAfter=2, keepWithNext=1),
        "li": ParagraphStyle("li", leftIndent=12, bulletIndent=2, spaceAfter=1.5, **base),
        "cel": ParagraphStyle("cel", fontName=f["sans"], fontSize=7.3, leading=9.2, textColor=INK),
        "celh": ParagraphStyle("celh", fontName=f["bold"], fontSize=7.3, leading=9.2, textColor=INK),
        "code": ParagraphStyle("code", fontName=f["mono"], fontSize=6.6, leading=8.1, textColor=INK, backColor=ZEBRA,
                               borderColor=LINE, borderWidth=0.4, borderPadding=4, spaceBefore=3, spaceAfter=6),
        "toc0": ParagraphStyle("toc0", fontName=f["bold"], fontSize=9.5, leading=14, leftIndent=0),
        "toc1": ParagraphStyle("toc1", fontName=f["sans"], fontSize=8.5, leading=12, leftIndent=14, textColor=MUTED),
    }


# ===========================================================================
# 4. Blocos básicos: nota, tabela, métricas, código
# ===========================================================================
def _para(txt, estilo, html_mode=False):
    try:
        return Paragraph(_html_inline(txt) if html_mode else _md_inline(txt), estilo)
    except Exception:                                                      # noqa: BLE001
        return Paragraph(_esc(re.sub(r"<[^>]+>", "", str(txt))), estilo)


def _nota(txt, tipo, S):
    fundo, borda = NOTAS.get(tipo, NOTAS[""])
    t = Table([[_para(txt, S["p"], html_mode=True)]], colWidths=[LARGURA])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(fundo)),
                           ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(borda)),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(borda)),
                           ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return [t, Spacer(1, 6)]


_BAD = ("falha", "falhou", "sem cobertura", "coberto, com falha", "não aprovado", "erro")
_WARN = ("atenção", "passou despercebido", "coberto, sem resultado", "sem oráculo", "equivalente", "aprovado com ressalvas",
         "não avaliado")
_GOOD = ("ok", "validado", "passou", "detectado", "aprovado")


def _cor_status(texto):
    t = limpar(texto).lower()
    for chaves, cor in ((_BAD, "#C0183F"), (_WARN, "#8F5600"), (_GOOD, "#0B7A4F")):
        if any(t == k or t.startswith(k + " ") or t.startswith(k + ",") or t.startswith(k + "(") for k in chaves):
            return colors.HexColor(cor)
    return None


def _tabela(cab, linhas, S, fonte=None, largura=None):
    cab = [limpar(c) for c in cab]
    corpo = [[limpar(c) for c in l] for l in linhas]
    n = len(cab)
    est, esth = S["cel"], S["celh"]
    if fonte:
        est = ParagraphStyle("cel2", parent=est, fontSize=fonte, leading=fonte * 1.25)
        esth = ParagraphStyle("celh2", parent=esth, fontSize=fonte, leading=fonte * 1.25)
    pesos, minimos = [], []
    for j in range(n):
        m = max([len(cab[j])] + [len(l[j]) for l in corpo if j < len(l)])
        pesos.append(min(max(m, 4), 46))
        palavras = [(w, False) for l in corpo if j < len(l) for w in re.split(r"\s+", l[j]) if w] + \
                   [(w, True) for w in re.split(r"\s+", cab[j]) if w]
        minimos.append(max([stringWidth(w, _FONTE["bold"] if b else _FONTE["sans"], esth.fontSize if b else est.fontSize)
                            for w, b in palavras] or [10]) + 8)
    larg = largura or LARGURA
    if sum(minimos) >= larg:                      # não cabe sem quebrar palavras: reduz proporcionalmente
        ws = [larg * m / sum(minimos) for m in minimos]
    else:                                         # mínimo de cada coluna + sobra distribuída pelo tamanho do conteúdo
        sobra = larg - sum(minimos)
        ws = [m + sobra * p / sum(pesos) for m, p in zip(minimos, pesos)]
    dados = [[Paragraph(_esc(c), esth) for c in cab]] + [
        [_para(c, est) if c else Paragraph("", est) for c in l] for l in corpo]
    t = Table(dados, colWidths=ws, repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), HEAD_BG), ("GRID", (0, 0), (-1, -1), 0.35, LINE),
              ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
              ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
    for i in range(1, len(dados)):
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
        for j, c in enumerate(corpo[i - 1]):
            cor = _cor_status(c)
            if cor is not None:
                dados[i][j] = Paragraph(f'<font color="{cor.hexval().replace("0x", "#")}"><b>{_esc(c)}</b></font>', est)
    t._argW = ws
    t.setStyle(TableStyle(estilo))
    return [t, Spacer(1, 7)]


def _df_para_tabela(df, hide_index, S):
    df = df.copy()
    if not hide_index and not isinstance(df.index, pd.RangeIndex):
        df.insert(0, df.index.name or "", df.index.astype(str))
    cab = [str(c) for c in df.columns]
    linhas = [["" if (isinstance(v, float) and v != v) or v is None else str(v) for v in r] for r in df.itertuples(index=False)]
    fonte = None
    if len(cab) > 12:
        fonte = 5.4
    elif len(cab) > 8:
        fonte = 6.4
    return _tabela(cab, linhas, S, fonte=fonte)


def _metricas(itens, S):
    f = _registrar_fontes()
    out = []
    for i in range(0, len(itens), 5):
        grupo = itens[i:i + 5]
        cels = []
        for lab, val, delta in grupo:
            tam = 11.5 if len(str(val)) <= 10 else (9.2 if len(str(val)) <= 14 else 7.6)
            txt = (f'<font size="6.2" color="#6B6B80">{_esc(lab).upper()}</font><br/>'
                   f'<font face="{f["mono"]}" size="{tam}"><b>{_esc(val)}</b></font>')
            if delta:
                txt += f'<br/><font size="6.6" color="#0B7A4F">{_esc(delta)}</font>'
            cels.append(Paragraph(txt, ParagraphStyle("m", fontName=f["sans"], fontSize=8, leading=13)))
        w = LARGURA / 5
        t = Table([cels + [""] * (5 - len(cels))], colWidths=[w] * 5)
        est = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
        for j in range(len(cels)):
            est += [("BOX", (j, 0), (j, 0), 0.5, LINE), ("LINEBEFORE", (j, 0), (j, 0), 3, ACCENT),
                    ("BACKGROUND", (j, 0), (j, 0), colors.white)]
        t.setStyle(TableStyle(est))
        out += [t, Spacer(1, 6)]
    return out


def _codigo(texto, S, numerar=False):
    f = _registrar_fontes()
    larg_car = int(LARGURA / (S["code"].fontSize * 0.602)) - 8
    linhas = []
    for n, ln in enumerate(str(texto).expandtabs(4).split("\n"), 1):
        pref = f"{n:>3}  " if numerar else ""
        pedacos = textwrap.wrap(ln, larg_car - len(pref), drop_whitespace=False, replace_whitespace=False) or [""]
        for k, p in enumerate(pedacos):
            linhas.append((pref if k == 0 else " " * len(pref)) + ("   " if k else "") + p)
    out = []
    for i in range(0, len(linhas), 55):
        out.append(Preformatted(limpar_codigo("\n".join(linhas[i:i + 55])), S["code"]))
    return out


def limpar_codigo(t):
    t = _EMOJI.sub("", t)
    if not _FONTE.get("unicode", True):
        for a, b in _TROCAS.items():
            t = t.replace(a, b)
        t = t.encode("latin-1", "replace").decode("latin-1")
    return t


# ===========================================================================
# 5. Markdown simples -> flowables
# ===========================================================================
def _md_para_flowables(texto, S):
    out, par = [], []
    linhas = str(texto).split("\n")
    i = 0

    def fecha():
        if par:
            out.append(_para(" ".join(par), S["p"]))
            par.clear()

    while i < len(linhas):
        ln = linhas[i]
        if ln.strip().startswith("|") and i + 1 < len(linhas) and re.match(r"^\s*\|?\s*:?-{2,}", linhas[i + 1]):
            fecha()
            bloco = []
            while i < len(linhas) and linhas[i].strip().startswith("|"):
                bloco.append(linhas[i])
                i += 1
            celulas = [[c.strip() for c in l.strip().strip("|").split("|")] for l in bloco]
            cab, corpo = celulas[0], [c for k, c in enumerate(celulas) if k >= 2]
            corpo = [c + [""] * (len(cab) - len(c)) for c in corpo]
            out += _tabela(cab, corpo, S)
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            fecha()
            nivel = min(max(len(m.group(1)), 3), 4) if len(m.group(1)) > 2 else 3
            out.append(_para(m.group(2), S["h3"] if nivel == 3 else S["h4"]))
        elif re.match(r"^\s*([-*]|\d+\.)\s+", ln):
            fecha()
            marca = "•" if re.match(r"^\s*[-*]\s+", ln) else re.match(r"^\s*(\d+\.)", ln).group(1)
            out.append(Paragraph(_md_inline(re.sub(r"^\s*([-*]|\d+\.)\s+", "", ln)), S["li"], bulletText=marca))
        elif not ln.strip():
            fecha()
        elif re.match(r"^\s*(---|___)\s*$", ln):
            fecha()
        else:
            par.append(ln.strip().lstrip(">").strip())
        i += 1
    fecha()
    return out


# ===========================================================================
# 6. Grafo de fluxo de controle (a partir do DOT gerado pelo engine)
# ===========================================================================
def _parse_dot(dot):
    nos, arestas = OrderedDict(), []
    for ln in dot.splitlines():
        ln = ln.strip()
        m = re.match(r'N(\d+) \[shape=(\w+), style="?[\w,]+"?, fillcolor="(#[0-9A-Fa-f]{6})", label="(.*)"\];', ln)
        if m:
            nos[int(m.group(1))] = {"forma": m.group(2), "fill": m.group(3), "rotulo": m.group(4).replace("\\n", "\n")}
            continue
        m = re.match(r'N(\d+) -> N(\d+) \[color="(#[0-9A-Fa-f]{6})", fontcolor="#[0-9A-Fa-f]{6}", penwidth=([\d.]+)(?:, label="(\w+)")?\];', ln)
        if m:
            arestas.append({"s": int(m.group(1)), "d": int(m.group(2)), "cor": m.group(3), "pen": float(m.group(4)),
                            "rot": m.group(5) or ""})
    return nos, arestas


class GrafoGFC(Flowable):
    """Desenha o GFC em camadas (sem depender do Graphviz)."""

    LW, LH, GAP, ESP = 128, 52, 26, 72

    def __init__(self, dot, altura_max=600):
        super().__init__()
        self.nos, self.arestas = _parse_dot(dot)
        self.altura_max = altura_max
        self.f = _registrar_fontes()
        self._layout()
        self.escala = 1.0

    # --- layout -------------------------------------------------------------
    def _layout(self):
        ids = list(self.nos)
        suc = {i: [] for i in ids}
        grau = {i: 0 for i in ids}
        for a in self.arestas:
            suc[a["s"]].append(a["d"])
            grau[a["d"]] += 1
        entradas = [i for i in ids if grau[i] == 0] or ids[:1]
        estado, voltas = {}, set()

        import sys
        sys.setrecursionlimit(max(2000, len(ids) * 10))

        def dfs(u):
            estado[u] = 1
            for v in suc[u]:
                if estado.get(v) == 1:
                    voltas.add((u, v))
                elif v not in estado:
                    dfs(v)
            estado[u] = 2

        for e in entradas + ids:
            if e not in estado:
                dfs(e)
        for a in self.arestas:
            a["volta"] = (a["s"], a["d"]) in voltas or a["s"] == a["d"]
        # camadas pelo caminho mais longo (ignorando arestas de retorno)
        pred = {i: [] for i in ids}
        for a in self.arestas:
            if not a["volta"]:
                pred[a["d"]].append(a["s"])
        camada = {}

        def cam(n):
            if n not in camada:
                camada[n] = 0 if not pred[n] else 1 + max(cam(p) for p in pred[n])
            return camada[n]

        for i in ids:
            cam(i)
        # nó de saída sempre na última camada
        saidas = [i for i in ids if self.nos[i]["forma"] == "doublecircle"]
        ultima = max(camada.values())
        for s in saidas:
            camada[s] = ultima
        # nós fictícios para arestas longas
        self.cadeias = []
        larg = {i: self.LW for i in ids}
        for a in self.arestas:
            if a["volta"]:
                self.cadeias.append(None)
                continue
            ch = [a["s"]]
            for l in range(camada[a["s"]] + 1, camada[a["d"]]):
                k = ("f", id(a), l)
                camada[k], larg[k] = l, 12
                ch.append(k)
            ch.append(a["d"])
            self.cadeias.append(ch)
        self.camada, self.larg = camada, larg
        n_cam = max(camada.values()) + 1
        camadas = [[] for _ in range(n_cam)]
        for k, l in camada.items():
            camadas[l].append(k)
        for l in range(n_cam):
            camadas[l].sort(key=lambda k: (isinstance(k, tuple), k if isinstance(k, int) else 0))
        viz_ac, viz_ab = {k: [] for k in camada}, {k: [] for k in camada}
        for ch in self.cadeias:
            if ch:
                for u, v in zip(ch, ch[1:]):
                    viz_ab[u].append(v)
                    viz_ac[v].append(u)

        def pos(l):
            return {k: i for i, k in enumerate(camadas[l])}

        def ordena(l, p, viz):
            atual = {k: i for i, k in enumerate(camadas[l])}      # posição atual (list.sort esvazia a lista durante a ordenação)
            camadas[l].sort(key=lambda k: (sum(p[x] for x in viz[k]) / len(viz[k])) if viz[k] else atual[k])

        for _ in range(6):
            for l in range(1, n_cam):
                ordena(l, pos(l - 1), viz_ac)
            for l in range(n_cam - 2, -1, -1):
                ordena(l, pos(l + 1), viz_ab)
        x = {}
        for l in range(n_cam):
            tot = sum(larg[k] for k in camadas[l]) + self.GAP * (len(camadas[l]) - 1)
            cx = -tot / 2
            for k in camadas[l]:
                x[k] = cx + larg[k] / 2
                cx += larg[k] + self.GAP

        def relaxa(l, vizinhos):
            alvo = {k: (sum(x[v] for v in vizinhos[k]) / len(vizinhos[k])) if vizinhos[k] else x[k] for k in camadas[l]}
            prev = None
            for k in camadas[l]:
                xk = alvo[k]
                if prev is not None:
                    xk = max(xk, x[prev] + (larg[prev] + larg[k]) / 2 + self.GAP)
                x[k] = xk
                prev = k

        for _ in range(8):
            for l in range(1, n_cam):
                relaxa(l, viz_ac)
            for l in range(n_cam - 2, -1, -1):
                relaxa(l, viz_ab)
        self.camadas, self.x = camadas, x
        esq = min(x[k] - larg[k] / 2 for k in x)
        dire = max(x[k] + larg[k] / 2 for k in x)
        n_voltas = sum(1 for a in self.arestas if a["volta"])
        self.margem_dir = 18 + 12 * n_voltas
        self.x0 = -esq + 8
        self.W = dire - esq + 16 + self.margem_dir
        self.H = (n_cam - 1) * self.ESP + self.LH + 16

    def _y(self, k):                      # topo = 0 (camada 0); devolve y do centro, crescendo para baixo
        return 8 + self.LH / 2 + self.camada[k] * self.ESP

    # --- Flowable -------------------------------------------------------------
    def wrap(self, aw, ah):
        self.escala = min(1.0, aw / self.W, min(ah, self.altura_max) / self.H)
        self.width, self.height = self.W * self.escala, self.H * self.escala
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.scale(self.escala, self.escala)

        def X(k):
            return self.x[k] + self.x0

        def Y(k):
            return self.H - self._y(k)

        # pontos de saída/entrada espalhados ao longo da base/topo de cada nó
        saidas, entradas = {}, {}
        for idx, ch in enumerate(self.cadeias):
            if ch:
                saidas.setdefault(ch[0], []).append((idx, X(ch[1])))
                entradas.setdefault(ch[-1], []).append((idx, X(ch[-2])))

        def anexo(lista, idx, centro_x, largura, diamante, topo):
            lista = sorted(lista, key=lambda t: t[1])
            k = len(lista)
            i = [t[0] for t in lista].index(idx)
            passo = min(26, (largura * 0.55) / max(k, 1))
            off = (i - (k - 1) / 2) * passo
            return off

        def ponto(no, idx, base):
            lista = (saidas if base else entradas).get(no, [])
            if self.nos[no]["forma"] == "doublecircle" or len(lista) < 1:
                off = 0
            else:
                off = anexo(lista, idx, X(no), self.LW, self.nos[no]["forma"] == "diamond", not base)
            cx, cy = X(no), Y(no)
            if self.nos[no]["forma"] == "diamond":
                a, b = self.LW / 2, self.LH / 2
                dy = b * (1 - min(abs(off), a) / a)
            elif self.nos[no]["forma"] == "doublecircle":
                dy = 10
            else:
                dy = self.LH / 2 - 2
            return cx + off, (cy - dy if base else cy + dy)

        # arestas
        for idx, a in enumerate(self.arestas):
            cor = colors.HexColor(a["cor"])
            c.setStrokeColor(cor)
            c.setFillColor(cor)
            c.setLineWidth(0.7 + (a["pen"] - 1.2) * 0.5)
            ch = self.cadeias[idx]
            if a["volta"]:
                s, d = a["s"], a["d"]
                n_v = [b for b in self.arestas if b["volta"]].index(a)
                bx = max(X(k) + self.larg[k] / 2 for k in self.x) + 12 + 12 * n_v
                # sai por baixo da origem, corre no vão entre camadas, sobe pela margem direita e entra por cima do destino
                s_base = Y(s) - (self.LH / 2 if self.nos[s]["forma"] == "diamond" else self.LH / 2 - 2)
                d_topo = Y(d) + (self.LH / 2 if self.nos[d]["forma"] == "diamond" else self.LH / 2 - 2)
                sx = X(s) + (0 if self.nos[s]["forma"] == "diamond" else 20)
                dx = X(d) + (0 if self.nos[d]["forma"] == "diamond" else 20)
                pts = [(sx, s_base), (sx, s_base - 9), (bx, s_base - 9), (bx, d_topo + 10), (dx, d_topo + 10), (dx, d_topo)]
            else:
                p0 = ponto(ch[0], idx, True)
                p1 = ponto(ch[-1], idx, False)
                pts = [p0] + [(X(k), Y(k)) for k in ch[1:-1]] + [p1]
            path = c.beginPath()
            path.moveTo(*pts[0])
            for p in pts[1:]:
                path.lineTo(*p)
            c.drawPath(path, stroke=1, fill=0)
            # ponta da seta
            (xa, ya), (xb, yb) = pts[-2], pts[-1]
            import math
            ang = math.atan2(yb - ya, xb - xa)
            seta = c.beginPath()
            seta.moveTo(xb, yb)
            seta.lineTo(xb - 6 * math.cos(ang - 0.4), yb - 6 * math.sin(ang - 0.4))
            seta.lineTo(xb - 6 * math.cos(ang + 0.4), yb - 6 * math.sin(ang + 0.4))
            seta.close()
            c.drawPath(seta, stroke=0, fill=1)
            if a["rot"]:
                c.setFont(self.f["bold"], 7.5)
                lx = pts[0][0] + (pts[1][0] - pts[0][0]) * 0.28 + 3
                ly = pts[0][1] + (pts[1][1] - pts[0][1]) * 0.28
                c.drawString(lx, ly - 2, a["rot"])
        # nós
        for no, d in self.nos.items():
            cx, cy = X(no), Y(no)
            c.setStrokeColor(colors.HexColor("#6B6B80"))
            c.setFillColor(colors.HexColor(d["fill"]))
            c.setLineWidth(0.8)
            linhas = d["rotulo"].split("\n")
            if d["forma"] == "diamond":
                a, b = self.LW / 2, self.LH / 2
                p = c.beginPath()
                p.moveTo(cx, cy + b)
                p.lineTo(cx + a, cy)
                p.lineTo(cx, cy - b)
                p.lineTo(cx - a, cy)
                p.close()
                c.drawPath(p, stroke=1, fill=1)
                quebra = 19
            elif d["forma"] == "doublecircle":
                c.circle(cx, cy, 13, stroke=1, fill=1)
                c.circle(cx, cy, 10, stroke=1, fill=0)
                c.setFillColor(INK)
                c.setFont(self.f["sans"], 6.6)
                c.drawCentredString(cx, cy - 2.3, "Fim")
                continue
            else:
                c.roundRect(cx - self.LW / 2, cy - self.LH / 2 + 2, self.LW, self.LH - 4, 6, stroke=1, fill=1)
                quebra = 27
            c.setFillColor(INK)
            texto = [(self.f["bold"], linhas[0])]
            resto = " ".join(linhas[1:])
            for w in textwrap.wrap(limpar_codigo(resto), quebra)[:2]:
                texto.append((self.f["sans"], w))
            y0 = cy + (len(texto) - 1) * 3.6 - 2
            for k, (fn, t) in enumerate(texto):
                c.setFont(fn, 6.4)
                c.drawCentredString(cx, y0 - k * 7.2, t)
        c.restoreState()


class GraficoAVL(Flowable):
    """Pontos de fronteira (On, Off, Interior, Exterior) numa reta numérica."""

    def __init__(self, pts, fronteira, largura=LARGURA):
        super().__init__()
        self.pts, self.fronteira, self.W, self.H = pts, float(fronteira), largura, 24 * len(pts) + 56

    def wrap(self, aw, ah):
        return self.W, self.H

    def draw(self):
        f = _registrar_fontes()
        c = self.canv
        vals = [float(p["valor"]) for p in self.pts] + [self.fronteira]
        lo, hi = min(vals), max(vals)
        if hi == lo:
            lo, hi = lo - 1, hi + 1
        esq, dire = 70, self.W - 60
        fx = lambda v: esq + (v - lo) / (hi - lo) * (dire - esq)
        topo = self.H - 14
        base = 26
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        for t in range(0, 11):
            v = lo + (hi - lo) * t / 10
            c.line(fx(v), base, fx(v), topo)
            c.setFillColor(MUTED)
            c.setFont(f["sans"], 6.4)
            c.drawCentredString(fx(v), base - 10, f"{v:g}")
        c.setDash(3, 2)
        c.setStrokeColor(ACCENT)
        c.setLineWidth(1)
        c.line(fx(self.fronteira), base, fx(self.fronteira), topo)
        c.setDash()
        ordem = sorted(self.pts, key=lambda p: float(p["valor"]))
        for i, p in enumerate(ordem):
            y = topo - 12 - i * 24
            bom = p["classe"] in ("Válida", "Ramo F")
            c.setFillColor(colors.HexColor("#1FAE8E" if bom else "#E5566A"))
            c.circle(fx(float(p["valor"])), y, 5, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont(f["sans"], 7)
            c.drawRightString(esq - 8, y - 2.4, limpar(p["ponto"]))
            c.setFont(f["mono"], 6.6)
            c.setFillColor(MUTED)
            c.drawString(fx(float(p["valor"])) + 8, y - 2.2, limpar(p["rotulo"]))


# ===========================================================================
# 7. Documento
# ===========================================================================
class _Numerada(rl_canvas.Canvas):
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for est in self._paginas:
            self.__dict__.update(est)
            f = _registrar_fontes()
            self.setFont(f["sans"], 7)
            self.setFillColor(MUTED)
            self.drawRightString(A4[0] - 36, 22, f"Página {self._pageNumber} de {total}")
            super().showPage()
        super().save()


class _Doc(BaseDocTemplate):
    def afterFlowable(self, fl):
        if isinstance(fl, Paragraph) and fl.style.name in ("H1", "H2") and getattr(fl, "_toc", False):
            self.notify("TOCEntry", (0 if fl.style.name == "H1" else 1, fl.getPlainText(), self.page))


def _cabecalho(meta):
    def f(canv, doc):
        fo = _registrar_fontes()
        canv.saveState()
        canv.setFillColor(ACCENT)
        canv.rect(36, A4[1] - 30, 4, 11, stroke=0, fill=1)
        canv.setFillColor(INK)
        canv.setFont(fo["bold"], 8.2)
        canv.drawString(46, A4[1] - 28, "TestingStudio Web")
        canv.setFillColor(MUTED)
        canv.setFont(fo["sans"], 7.2)
        canv.drawRightString(A4[0] - 36, A4[1] - 28, limpar(meta.get("unidade", "")))
        canv.setStrokeColor(LINE)
        canv.setLineWidth(0.5)
        canv.line(36, A4[1] - 34, A4[0] - 36, A4[1] - 34)
        canv.drawString(36, 22, f"Gerado em {meta.get('gerado_em', '')}")
        canv.restoreState()
    return f


def _marcador(texto, estilo, toc=True):
    p = Paragraph(_esc(texto), estilo)
    p._toc = toc
    return p


def build_pdf(blocos, meta=None) -> bytes:
    meta = dict(meta or {})
    for b in blocos:
        if b and b[0] == "meta":
            meta.update(b[1])
    meta.setdefault("gerado_em", datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-3))).strftime("%d/%m/%Y %H:%M"))  # horário de Brasília
    _registrar_fontes()
    S = _estilos()
    story, buffer_metricas = [], []

    def flush_metricas():
        if buffer_metricas:
            story.extend(_metricas(buffer_metricas, S))
            buffer_metricas.clear()

    # --- capa ------------------------------------------------------------------
    fo = _registrar_fontes()
    story.append(Spacer(1, 70))
    story.append(Paragraph("TestingStudio Web", ParagraphStyle("T", fontName=fo["bold"], fontSize=30, leading=34, textColor=INK)))
    story.append(Paragraph("Relatório completo da análise", ParagraphStyle("T2", fontName=fo["sans"], fontSize=15, leading=20,
                                                                          textColor=ACCENT, spaceAfter=18)))
    linhas_meta = [("Unidade analisada", meta.get("unidade", "—")), ("Arquivo", meta.get("arquivo", "—")),
                   ("Linhas do fonte", str(meta.get("linhas", "—"))), ("SHA-256 (início)", meta.get("sha", "—")),
                   ("Gerado em", meta["gerado_em"])]
    t = Table([[Paragraph(f"<b>{_esc(a)}</b>", S["cel"]), Paragraph(_esc(b), S["cel"])] for a, b in linhas_meta],
              colWidths=[110, LARGURA - 110])
    t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [t, Spacer(1, 22), Paragraph("Conteúdo", S["h3"])]
    toc = TableOfContents()
    toc.levelStyles = [S["toc0"], S["toc1"]]
    story += [toc, PageBreak()]

    # --- corpo -----------------------------------------------------------------
    i, n = 0, len(blocos)
    primeiro_tab = True
    ultimo_tab = ""
    while i < n:
        b = blocos[i]
        tipo = b[0]
        if tipo != "metric":
            flush_metricas()
        if tipo == "meta":
            pass
        elif tipo == "tab":
            _, nivel, rot = b
            ultimo_tab = rot
            if nivel == 2 and rot.startswith("Parecer do Gemini"):
                j = i + 1
                tem_texto = False
                while j < n and blocos[j][0] != "tab":
                    tem_texto = tem_texto or blocos[j][0] == "md"
                    j += 1
                if not tem_texto:
                    i = j
                    continue
            if nivel == 1:
                if not primeiro_tab:
                    story.append(PageBreak())
                primeiro_tab = False
                story.append(_marcador(rot, S["h1"]))
                tt = Table([[""]], colWidths=[LARGURA], rowHeights=[2])
                tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT)]))
                story += [tt, Spacer(1, 8)]
            else:
                story.append(_marcador(rot, S["h2"]))
        elif tipo == "exp":
            rot = limpar(b[1])
            if b[1].startswith("🤖"):
                # só aparece se houver parecer gerado (markdown logo após a legenda)
                j = i + 1
                if j < n and blocos[j][0] == "cap":
                    j += 1
                if j < n and blocos[j][0] == "md":
                    if not ultimo_tab.startswith("Parecer do Gemini"):
                        story.append(_para("Parecer do Gemini (IA)", S["h3"]))
                    story.append(_para("Texto gerado por IA a partir dos resultados; deve ser conferido.", S["cap"]))
                    story += _md_para_flowables(blocos[j][1], S)
                    i = j
            elif rot.startswith("Visualizar o documento"):
                pass
            else:
                story.append(_para(rot, S["h3"]))
        elif tipo == "h":
            story.append(_para(b[2], S["h2"] if b[1] <= 2 else S["h3"]))
            story[-1].keepWithNext = True
        elif tipo == "cap":
            if not (b[1].startswith("A IA revisa os resultados") or b[1].strip() == "TestingStudio Web"):
                story.append(_para(b[1], S["cap"]))
        elif tipo == "md":
            m = re.match(r'^<div class="note\s*(\w*)">(.*)</div>\s*$', b[1], flags=re.S)
            if m:
                story += _nota(m.group(2), m.group(1), S)
            else:
                story += _md_para_flowables(b[1], S)
        elif tipo == "df":
            story += _df_para_tabela(b[1], b[2], S)
        elif tipo == "metric":
            buffer_metricas.append((b[1], b[2], b[3]))
        elif tipo == "code":
            story += _codigo(b[1], S)
        elif tipo == "src":
            story += _codigo(b[1], S, numerar=True)
        elif tipo == "par":
            story.append(_para(f"**{b[1]}:** `{b[2]}`", S["p"]))
        elif tipo == "dot":
            try:
                story += [GrafoGFC(b[1]), Spacer(1, 6)]
            except Exception as ex:                                        # noqa: BLE001
                story.append(_para(f"(Não foi possível desenhar o grafo: {ex})", S["cap"]))
        elif tipo == "avl":
            story += [GraficoAVL(b[1]["pontos"], b[1]["fronteira"]), Spacer(1, 6)]
        i += 1
    flush_metricas()

    buf = io.BytesIO()
    doc = _Doc(buf, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=46, bottomMargin=40,
               title="TestingStudio Web: relatório completo", author="TestingStudio Web")
    doc.addPageTemplates([PageTemplate("p", [Frame(36, 40, LARGURA, A4[1] - 86, id="f", leftPadding=0, rightPadding=0,
                                                   topPadding=0, bottomPadding=0)], onPage=_cabecalho(meta))])
    doc.multiBuild(story, canvasmaker=_Numerada)
    return buf.getvalue()


def pdf_ou_erro(blocos, meta=None) -> bytes:
    """Nunca levanta: se algo falhar, devolve um PDF de uma página explicando o erro."""
    try:
        return build_pdf(blocos, meta)
    except Exception as ex:                                                # noqa: BLE001
        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=A4)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(48, A4[1] - 80, "Não foi possível gerar o relatório em PDF.")
        c.setFont("Helvetica", 10)
        for k, ln in enumerate(textwrap.wrap(f"{type(ex).__name__}: {ex}", 95)):
            c.drawString(48, A4[1] - 110 - 14 * k, ln.encode("latin-1", "replace").decode("latin-1"))
        c.save()
        return buf.getvalue()
