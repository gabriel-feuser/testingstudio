"""
engine.py — Motor determinístico do TestingStudio Web.

Tudo aqui é calculado em Python puro (sem IA):
  Módulo 1  Caixa-preta : épsilon, PCE, AVL, suíte de testes com oráculo
  Módulo 2  Caixa-branca: Grafo de Fluxo de Controle (GFC) e V(G) de McCabe
  Módulo 3  Fluxo de dados (pares Def-Uso) e Teste de Mutação (MS)

O Gemini entra apenas como "parceiro de pareamento" (parecer opcional).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal as D, ROUND_HALF_UP
from itertools import product

import networkx as nx
import numpy as np

# ---------------------------------------------------------------------------
# 1. Leitura do fonte Informix-4GL
# ---------------------------------------------------------------------------
STMT_KEYWORDS = {
    "LET", "CALL", "RETURN", "INSERT", "UPDATE", "DELETE", "SELECT", "BEGIN",
    "COMMIT", "ROLLBACK", "WHENEVER", "MESSAGE", "INITIALIZE", "DISPLAY",
    "ERROR", "OPEN", "CLOSE", "FETCH", "PREPARE", "EXECUTE", "DECLARE",
    "LOCATE", "PROMPT", "INPUT", "MENU", "EXIT", "CONTINUE", "SLEEP", "LOCK",
    "UNLOCK", "FREE", "PUT", "FLUSH", "RUN", "LOAD", "UNLOAD", "OUTPUT",
    "START", "FINISH", "REPORT", "DEFINE", "DATABASE", "GLOBALS", "MAIN",
}
TYPE_WORDS = {
    "DECIMAL", "DEC", "NUMERIC", "MONEY", "INTEGER", "INT", "SMALLINT",
    "CHAR", "VARCHAR", "DATE", "FLOAT", "SMALLFLOAT", "DATETIME", "INTERVAL",
}


def clean_line(line: str) -> str:
    """Remove comentários (# e --) e mascara o conteúdo de strings."""
    out, q, i = [], None, 0
    while i < len(line):
        c = line[i]
        if q:
            if c == q:
                q = None
                out.append('"…"')
        else:
            if c in "\"'":
                q = c
            elif c == "#" or line[i:i + 2] == "--":
                break
            else:
                out.append(c)
        i += 1
    return "".join(out).strip()


def _split_commas(txt: str):
    parts, depth, cur = [], 0, ""
    for ch in txt:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        parts.append(cur.strip())
    return parts


def parse_defines(defines):
    items = []
    for d in defines:
        items += _split_commas(re.sub(r"(?i)^DEFINE\b", "", d).strip())
    types, pending = {}, []
    for it in items:
        m = re.match(r"^(\w+)\s+(\w+)\s*(?:\(\s*(\d+)\s*(?:,\s*(\d+))?\s*\))?", it)
        if m and m.group(2).upper() in TYPE_WORDS:
            t = (m.group(2).upper(),
                 int(m.group(3)) if m.group(3) else None,
                 int(m.group(4)) if m.group(4) else 0)
            for name in pending + [m.group(1)]:
                types[name] = t
            pending = []
        else:
            nm = re.match(r"^(\w+)\s*$", it)
            if nm:
                pending.append(nm.group(1))
    return types


@dataclass
class Func:
    name: str
    params: list
    lines: list            # corpo limpo (sem DEFINE)
    defines: list
    start: int
    end: int
    types: dict = field(default_factory=dict)

    @property
    def variables(self):
        return list(dict.fromkeys(list(self.params) + list(self.types)))

    @property
    def locals(self):
        return [v for v in self.variables if v not in self.params]


def split_functions(text: str):
    funcs, cur = [], None
    for idx, raw in enumerate(text.splitlines(), start=1):
        line = clean_line(raw)
        m = re.match(r"(?i)^FUNCTION\s+(\w+)\s*\((.*)\)\s*$", line)
        if m and cur is None:
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            cur = {"name": m.group(1), "params": params, "body": [], "start": idx}
            continue
        if cur is not None:
            if re.match(r"(?i)^END\s+FUNCTION\b", line):
                funcs.append(_finish(cur, idx))
                cur = None
            elif line:
                cur["body"].append(line)
    return funcs


def _finish(cur, end):
    defines, body, cont = [], [], False
    for ln in cur["body"]:
        if cont:
            defines[-1] += " " + ln
            cont = ln.rstrip().endswith(",")
        elif re.match(r"(?i)^DEFINE\b", ln):
            defines.append(ln)
            cont = ln.rstrip().endswith(",")
        else:
            body.append(ln)
    return Func(cur["name"], cur["params"], body, defines, cur["start"], end,
                parse_defines(defines))


# ---------------------------------------------------------------------------
# 2. Tokenização estrutural e Grafo de Fluxo de Controle
# ---------------------------------------------------------------------------
def tokenize(lines):
    toks = []
    for ln in lines:
        s = re.sub(r"(?i)\bEND\s+IF\b", "ENDIF", ln)
        s = re.sub(r"(?i)\bEND\s+(WHILE|FOREACH|FOR)\b", r"ENDLOOP", s)
        first = True
        while True:
            s = s.strip()
            if not s:
                break
            m = re.match(r"(?i)^IF\b(.*?)\bTHEN\b(.*)$", s)
            if m:
                toks.append(("IF", m.group(1).strip()))
                s, first = m.group(2), False
                continue
            if re.match(r"(?i)^ELSE\b", s):
                toks.append(("ELSE", ""))
                s, first = s[4:], False
                continue
            if re.match(r"(?i)^ENDIF\b", s):
                toks.append(("ENDIF", ""))
                s, first = s[5:], False
                continue
            if re.match(r"(?i)^ENDLOOP\b", s):
                toks.append(("ENDLOOP", ""))
                s, first = s[7:], False
                continue
            if re.match(r"(?i)^(WHILE|FOREACH|FOR)\b", s):
                toks.append(("LOOP", s))
                break
            cut = re.search(r"(?i)\b(ELSE|ENDIF|ENDLOOP)\b", s)
            chunk, s = (s[:cut.start()], s[cut.start():]) if cut else (s, "")
            chunk = chunk.strip()
            if not chunk:
                continue
            word = re.match(r"(\w+)", chunk)
            starts_stmt = bool(word and word.group(1).upper() in STMT_KEYWORDS)
            if first and not starts_stmt and toks and toks[-1][0] == "STMT":
                toks[-1] = ("STMT", toks[-1][1] + " " + chunk)
            else:
                kind = "RETURN" if re.match(r"(?i)^RETURN\b", chunk) else "STMT"
                toks.append((kind, chunk))
            first = False
    return toks


@dataclass
class Node:
    id: int
    kind: str                      # block | pred | exit
    stmts: list = field(default_factory=list)
    cond: str = ""


@dataclass
class CFG:
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)      # (src, dst, label)
    entry: int | None = None
    exit: int | None = None
    returns: list = field(default_factory=list)
    params: list = field(default_factory=list)
    locals: list = field(default_factory=list)
    variables: list = field(default_factory=list)


def _strip_outer(e: str) -> str:
    e = e.strip()
    while e.startswith("(") and e.endswith(")"):
        depth = 0
        ok = True
        for i, ch in enumerate(e):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and i < len(e) - 1:
                ok = False
                break
        if not ok:
            break
        e = e[1:-1].strip()
    return e


def _split_top(expr: str, op: str):
    parts, depth, cur = [], 0, 0
    for m in re.finditer(r"\(|\)|\b(?:OR|AND)\b", expr, re.I):
        t = m.group(0)
        if t == "(":
            depth += 1
        elif t == ")":
            depth -= 1
        elif depth == 0 and t.upper() == op:
            parts.append(expr[cur:m.start()])
            cur = m.end()
    parts.append(expr[cur:])
    return [p.strip() for p in parts]


class _Builder:
    def __init__(self, toks, decompose):
        self.toks, self.i, self.decomp = toks, 0, decompose
        self.cfg = CFG()

    # -- infraestrutura -----------------------------------------------------
    def new(self, kind, **kw):
        nid = len(self.cfg.nodes) + 1
        self.cfg.nodes[nid] = Node(nid, kind, **kw)
        return nid

    def connect(self, pending, dst):
        for src, label in pending:
            if src is None:
                self.cfg.entry = dst
            else:
                self.cfg.edges.append((src, dst, label))

    def simple(self, pending, text, is_return):
        if not pending:
            return pending                      # código inalcançável
        if (len(pending) == 1 and pending[0][0] is not None and pending[0][1] == ""
                and self.cfg.nodes[pending[0][0]].kind == "block"):
            n = pending[0][0]
        else:
            n = self.new("block")
            self.connect(pending, n)
        self.cfg.nodes[n].stmts.append(text)
        if is_return:
            self.cfg.returns.append(n)
            return []
        return [(n, "")]

    def cond(self, expr):
        """Decompõe a condição (curto-circuito). -> (entrada, V-pend, F-pend)"""
        e = _strip_outer(expr)
        if self.decomp:
            ors = _split_top(e, "OR")
            if len(ors) > 1:
                acc = self.cond(ors[0])
                for p in ors[1:]:
                    b = self.cond(p)
                    self.connect(acc[2], b[0])
                    acc = (acc[0], acc[1] + b[1], b[2])
                return acc
            ands = _split_top(e, "AND")
            if len(ands) > 1:
                acc = self.cond(ands[0])
                for p in ands[1:]:
                    b = self.cond(p)
                    self.connect(acc[1], b[0])
                    acc = (acc[0], b[1], acc[2] + b[2])
                return acc
        n = self.new("pred", cond=e)
        return n, [(n, "V")], [(n, "F")]

    def skip(self):
        depth = 1
        while self.i < len(self.toks) and depth:
            k = self.toks[self.i][0]
            depth += k in ("IF", "LOOP")
            depth -= k in ("ENDIF", "ENDLOOP")
            self.i += 1

    # -- parser recursivo ---------------------------------------------------
    def block(self, pending, stops):
        while self.i < len(self.toks):
            kind, text = self.toks[self.i]
            if kind in stops:
                break
            self.i += 1
            if kind in ("ELSE", "ENDIF", "ENDLOOP"):
                continue
            if kind in ("STMT", "RETURN"):
                pending = self.simple(pending, text, kind == "RETURN")
            elif kind == "IF":
                if not pending:
                    self.skip()
                    continue
                entry, tp, fp = self.cond(text)
                self.connect(pending, entry)
                tp = self.block(tp, {"ELSE", "ENDIF"})
                if self.i < len(self.toks) and self.toks[self.i][0] == "ELSE":
                    self.i += 1
                    fp = self.block(fp, {"ENDIF"})
                if self.i < len(self.toks) and self.toks[self.i][0] == "ENDIF":
                    self.i += 1
                pending = tp + fp
            elif kind == "LOOP":
                if not pending:
                    self.skip()
                    continue
                m = re.match(r"(?i)^WHILE\b(.*)$", text)
                if m:
                    entry, tp, fp = self.cond(m.group(1))
                else:
                    n = self.new("pred", cond=text)
                    entry, tp, fp = n, [(n, "V")], [(n, "F")]
                self.connect(pending, entry)
                tp = self.block(tp, {"ENDLOOP"})
                if self.i < len(self.toks) and self.toks[self.i][0] == "ENDLOOP":
                    self.i += 1
                self.connect(tp, entry)          # aresta de retorno do laço
                pending = fp
        return pending

    def run(self):
        pending = self.block([(None, "")], set())
        ex = self.new("exit")
        self.cfg.exit = ex
        self.connect(pending, ex)
        for r in self.cfg.returns:
            self.cfg.edges.append((r, ex, ""))
        return self.cfg


def build_cfg(func: Func, decompose: bool = True) -> CFG:
    cfg = _Builder(tokenize(func.lines), decompose).run()
    cfg.params, cfg.locals, cfg.variables = func.params, func.locals, func.variables
    return cfg


def count_faces(cfg: CFG):
    """Conta regiões (R) pela teoria de grafos planares (independe de E-N+2)."""
    G = nx.Graph()
    for i, (u, v, _l) in enumerate(cfg.edges):        # subdivide: evita multi-arestas
        G.add_edge(("n", u), ("m", i))
        G.add_edge(("m", i), ("n", v))
    if G.number_of_nodes() == 0 or not nx.is_connected(G):
        return None
    ok, emb = nx.check_planarity(G)
    if not ok:
        return None
    seen, faces = set(), 0
    for u, v in emb.edges():
        if (u, v) not in seen:
            emb.traverse_face(u, v, mark_half_edges=seen)
            faces += 1
    return faces


def mccabe(cfg: CFG) -> dict:
    N, E = len(cfg.nodes), len(cfg.edges)
    outdeg = {n: 0 for n in cfg.nodes}
    for s, _d, _l in cfg.edges:
        outdeg[s] += 1
    P = sum(1 for n in outdeg if outdeg[n] >= 2)
    R = count_faces(cfg)
    v1, v2 = E - N + 2, sum(max(outdeg[n] - 1, 0) for n in outdeg) + 1
    return {"N": N, "E": E, "P": P, "R": R, "V_EN": v1, "V_P": v2,
            "V_R": R, "consistente": R is not None and v1 == v2 == R}


def complexity_level(v: int) -> str:
    if v <= 10:
        return "Simples — baixo risco"
    if v <= 20:
        return "Moderada — risco moderado"
    if v <= 50:
        return "Alta — alto risco"
    return "Intestável"


def basis_paths(cfg: CFG, target: int, limit: int = 4000):
    outs = {n: [] for n in cfg.nodes}
    for i, (s, d, l) in enumerate(cfg.edges):
        outs[s].append((i, d))
    paths = []

    def dfs(n, used, seq):
        if len(paths) >= limit:
            return
        if n == cfg.exit:
            paths.append(list(seq))
            return
        for ei, d in outs[n]:
            if ei in used:
                continue
            used.add(ei)
            seq.append(ei)
            dfs(d, used, seq)
            seq.pop()
            used.discard(ei)

    if cfg.entry is not None:
        dfs(cfg.entry, set(), [])
    E = len(cfg.edges)
    paths.sort(key=len)
    chosen, M, rank = [], np.zeros((0, E)), 0
    for p in paths:
        v = np.zeros(E)
        for ei in p:
            v[ei] += 1
        M2 = np.vstack([M, v])
        r = np.linalg.matrix_rank(M2)
        if r > rank:
            M, rank = M2, r
            chosen.append(p)
        if rank >= target:
            break
    return chosen, len(paths)


def path_nodes(cfg: CFG, path):
    if not path:
        return []
    return [cfg.edges[path[0]][0]] + [cfg.edges[e][1] for e in path]


def node_label(node: Node, maxlen=34) -> str:
    if node.kind == "exit":
        return "Fim"
    if node.kind == "pred":
        txt = node.cond
    else:
        txt = node.stmts[0] if node.stmts else ""
        txt = re.sub(r"\s+", " ", txt)
        if len(node.stmts) > 1:
            txt += f"  (+{len(node.stmts) - 1})"
    return (txt[:maxlen] + "…") if len(txt) > maxlen else txt


def to_dot(cfg: CFG, covered_nodes=None, covered_edges=None) -> str:
    cn, ce = covered_nodes, covered_edges
    L = ['digraph G {', 'rankdir=TB;', 'bgcolor="transparent";',
         'node [fontname="Helvetica", fontsize=11, penwidth=1.4, fontcolor="#14213D", color="#5B6B85"];',
         'edge [fontname="Helvetica", fontsize=10];']
    for nid, nd in cfg.nodes.items():
        txt = node_label(nd).replace('"', "'")
        covered = cn is None or nid in cn
        if nd.kind == "pred":
            fill = "#F4CDD1" if covered else "#EEF2F8"
            L.append(f'N{nid} [shape=diamond, style=filled, fillcolor="{fill}", label="N{nid}\\n{txt}"];')
        elif nd.kind == "exit":
            L.append(f'N{nid} [shape=doublecircle, style=filled, fillcolor="#BFE5DA", label="Fim"];')
        else:
            fill = "#C9D8F0" if covered else "#EEF2F8"
            L.append(f'N{nid} [shape=box, style="rounded,filled", fillcolor="{fill}", label="N{nid}\\n{txt}"];')
    for i, (s, d, l) in enumerate(cfg.edges):
        col = {"V": "#1FAE8E", "F": "#E5566A"}.get(l, "#8795AE")
        pen = 2.4 if (ce is not None and i in ce) else 1.2
        lab = f', label="{l}"' if l else ""
        L.append(f'N{s} -> N{d} [color="{col}", fontcolor="{col}", penwidth={pen}{lab}];')
    L.append("}")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# 3. Execução do GFC (interpretador do subconjunto LET / RETURN / IF)
# ---------------------------------------------------------------------------
class Unsupported(Exception):
    pass


def _to_py(expr: str) -> str:
    e = expr
    e = re.sub(r"(?i)\b([A-Za-z_][\w.]*)\s+IS\s+NOT\s+NULL\b", r"(\1 is not None)", e)
    e = re.sub(r"(?i)\b([A-Za-z_][\w.]*)\s+IS\s+NULL\b", r"(\1 is None)", e)
    e = e.replace("<>", "!=")
    e = re.sub(r"(?<![<>!=])=(?!=)", "==", e)
    e = re.sub(r"(?i)\bOR\b", " or ", e)
    e = re.sub(r"(?i)\bAND\b", " and ", e)
    e = re.sub(r"(?i)\bNOT\b", " not ", e)
    e = re.sub(r"(?i)\bTRUE\b", "True", e)
    e = re.sub(r"(?i)\bFALSE\b", "False", e)
    e = re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)", r"D('\1')", e)
    return e


def _eval(expr, env):
    try:
        return eval(_to_py(expr), {"__builtins__": {}, "D": D}, env)
    except NameError as ex:
        raise Unsupported(str(ex))


def is_executable(cfg: CFG) -> bool:
    for nd in cfg.nodes.values():
        for s in nd.stmts:
            if not re.match(r"(?i)^(LET\s+\w+\s*=|RETURN\b)", s):
                return False
            if re.search(r"\w+\.\w+|\w+\s*\(", re.sub(r"D\(|\d+\.\d+", "", s)):
                return False
        if nd.kind == "pred" and re.search(r"\w+\.\w+|\w+\s*\(", nd.cond):
            return False
    return True


def run_cfg(cfg: CFG, args, scale=2, max_steps=500):
    q = D(1).scaleb(-scale)
    env = {v: None for v in cfg.locals}
    env.update(zip(cfg.params, args))
    outs = {n: [] for n in cfg.nodes}
    for i, (s, d, l) in enumerate(cfg.edges):
        outs[s].append((i, d, l))
    n, trace, taken, result, steps = cfg.entry, [], [], None, 0
    while True:
        trace.append(n)
        nd = cfg.nodes[n]
        if nd.kind == "exit":
            break
        steps += 1
        if steps > max_steps:
            raise RuntimeError("laço não terminou")
        if nd.kind == "block":
            for s in nd.stmts:
                m = re.match(r"(?i)^LET\s+(\w+)\s*=\s*(.*)$", s)
                if m:
                    val = _eval(m.group(2), env)
                    env[m.group(1)] = (val.quantize(q, rounding=ROUND_HALF_UP)
                                       if isinstance(val, D) else val)
                else:
                    expr = re.sub(r"(?i)^RETURN\b", "", s).strip()
                    result = _eval(expr, env) if expr else None
                    break
            choice = outs[n][0]
        else:
            try:
                truth = bool(_eval(nd.cond, env))
            except TypeError:                 # comparação com NULL => falso
                truth = False
            choice = next(o for o in outs[n] if o[2] == ("V" if truth else "F"))
        taken.append(choice[0])
        n = choice[1]
    return {"result": result, "trace": trace, "edges": taken}


# ---------------------------------------------------------------------------
# 4. Módulo 1 — Caixa-preta: épsilon, PCE, AVL, suíte e oráculo
# ---------------------------------------------------------------------------
def detect_decimal(func: Func | None, text: str = ""):
    """Retorna (precisão, escala) do primeiro DECIMAL do corpo/arquivo."""
    cand = [t for t in (func.types.values() if func else []) if t[0] in ("DECIMAL", "DEC", "NUMERIC", "MONEY")]
    if cand:
        return cand[0][1] or 12, cand[0][2]
    m = re.search(r"(?i)DECIMAL\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
    return (int(m.group(1)), int(m.group(2))) if m else (12, 2)


def epsilon_info(precision: int, scale: int) -> dict:
    eps = D(1).scaleb(-scale)
    return {"precision": precision, "scale": scale, "epsilon": eps,
            "max": D(10) ** (precision - scale) - eps}


def fmt(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, D):
        return format(v, ".2f").replace(".", ",")
    return str(v)


def _invalid(op, c, x):
    return {"<": x < c, "<=": x <= c, ">": x > c, ">=": x >= c}[op]


def derive_rules(func: Func, eps: D):
    """Descobre as fronteiras no código (var OP literal) e gera On/Off/Interior/Exterior."""
    found = {}
    for ln in func.lines:
        for m in re.finditer(r"(?i)\b([A-Za-z_][\w.]*)\s*(<=|>=|<|>)\s*(-?\d+(?:\.\d+)?)", ln):
            found.setdefault((m.group(2), D(m.group(3))), set()).add(m.group(1))
    rules = []
    for (op, c), vs in found.items():
        inv_below = op in ("<", "<=")
        on = c
        off = {"<": c - eps, "<=": c + eps, ">": c + eps, ">=": c - eps}[op]
        interior = c + 100 if inv_below else c - 100
        exterior = c - 100 if inv_below else c + 100
        pts = []
        for nome, val in (("On", on), ("Off", off), ("Interior", interior), ("Exterior", exterior)):
            bad = _invalid(op, c, val)
            pts.append({"ponto": nome, "valor": val,
                        "classe": "Inválida" if bad else "Válida",
                        "esperado": "Erro (-1)" if bad else "Sucesso (cálculo OK)"})
        rules.append({"op": op, "c": c, "vars": sorted(vs), "points": pts,
                      "inv_below": inv_below, "from_code": True})
    if not rules:  # fallback: regra do manual
        pts = []
        for nome, val in (("On", D(0)), ("Off", -eps), ("Interior", D(100)), ("Exterior", D(-100))):
            bad = val < 0
            pts.append({"ponto": nome, "valor": val, "classe": "Inválida" if bad else "Válida",
                        "esperado": "Erro (-1)" if bad else "Sucesso (cálculo OK)"})
        rules.append({"op": "<", "c": D(0), "vars": [], "points": pts,
                      "inv_below": True, "from_code": False})
    return rules


def range_text(op, c, invalid: bool):
    sym = {"<": ("<", "≥"), "<=": ("≤", ">"), ">": (">", "≤"), ">=": ("≥", "<")}[op]
    return f"x {sym[0] if invalid else sym[1]} {fmt(c)}"


def build_pce(func: Func, rule) -> list:
    rows = []
    has_null = any(re.search(r"(?i)\bIS\s+NULL\b", ln) for ln in func.lines)
    pts = {p["ponto"]: p["valor"] for p in rule["points"]}
    valid_rep = pts["Interior"] if not _invalid(rule["op"], rule["c"], pts["Interior"]) else pts["Exterior"]
    invalid_rep = pts["Exterior"] if valid_rep == pts["Interior"] else pts["Interior"]
    for p in func.params:
        rows += [
            {"Entrada": p, "Classe": "C1 · Faixa válida", "Faixa": range_text(rule["op"], rule["c"], False),
             "Tipo": "Válida", "Representante": fmt(valid_rep),
             "Justificativa": "Região em que o código segue para a fórmula."},
            {"Entrada": p, "Classe": "C2 · Faixa inválida", "Faixa": range_text(rule["op"], rule["c"], True),
             "Tipo": "Inválida", "Representante": fmt(invalid_rep),
             "Justificativa": "Região rejeitada pela validação (retorno -1)." if rule["from_code"]
             else "Regra do manual — o código NÃO valida esta faixa."},
            {"Entrada": p, "Classe": "C3 · Nulo", "Faixa": "NULL",
             "Tipo": "Válida (tratada como 0)" if has_null else "Inválida",
             "Representante": "NULL",
             "Justificativa": "O código converte NULL em 0 antes da validação." if has_null
             else "Nenhum tratamento de NULL encontrado no código."},
        ]
    return rows


def oracle(args) -> D:
    """Oráculo EXTERNO (regra de negócio do manual) — nunca o código-fonte."""
    vals = [D(0) if a is None else a for a in args]
    if any(v < 0 for v in vals):
        return D(-1)
    return (vals[0] * vals[1] + vals[2]).quantize(D("0.01"), rounding=ROUND_HALF_UP)


BASE = [D("10.00"), D("5.00"), D("3.00")]


def build_suite(rule, eps: D, n_params=3):
    cases = []

    def add(tec, desc, args):
        cases.append({"id": f"CT{len(cases) + 1:02d}", "tecnica": tec,
                      "descricao": desc, "args": tuple(args), "esperado": oracle(args)})

    add("PCE", "Todos os parâmetros na classe válida", BASE)
    for i in range(n_params):
        a = list(BASE)
        a[i] = None
        add("PCE", f"Parâmetro {i + 1} nulo", a)
    for i in range(n_params):
        for p in rule["points"]:
            a = list(BASE)
            a[i] = p["valor"]
            add("AVL", f"Parâmetro {i + 1} no ponto {p['ponto']}", a)
    for i in range(n_params):
        a = list(BASE)
        a[i] = rule["c"] + eps
        add("AVL", f"Parâmetro {i + 1} em On + ε", a)
    add("PCE", "Todos zerados", [D(0)] * n_params)
    add("PCE", "Todos negativos", [D(-1)] * n_params)
    return cases


def run_suite(cfg: CFG, cases, scale=2):
    rows = []
    for c in cases:
        try:
            r = run_cfg(cfg, c["args"], scale)
            obtido, trace, edges, err = r["result"], r["trace"], r["edges"], ""
        except Exception as ex:                       # noqa: BLE001
            obtido, trace, edges, err = None, [], [], type(ex).__name__
        ok = (not err) and obtido is not None and obtido == c["esperado"]
        rows.append({**c, "obtido": obtido, "erro": err, "ok": ok,
                     "trace": trace, "edges": edges})
    return rows


# ---------------------------------------------------------------------------
# 5. Módulo 3a — Fluxo de dados (pares Def-Uso)
# ---------------------------------------------------------------------------
_IDENT = re.compile(r"[A-Za-z_]\w*(?:\.\w+)?")


def _idents(text, known):
    return [t for t in _IDENT.findall(text) if t in known or "." in t]


def _stmt_defuse(s, known):
    m = re.match(r"(?is)^LET\s+([\w.]+)\s*=\s*(.*)$", s)
    if m:
        return _idents(m.group(2), known), [m.group(1)]
    if re.match(r"(?i)^RETURN\b", s):
        return _idents(s[6:], known), []
    if re.match(r"(?i)^(INSERT|UPDATE|DELETE|SELECT)\b", s):
        return _idents(s, known), ["sqlca.sqlcode"]
    m = re.match(r"(?is)^CALL\s+\w+\s*\((.*)\)\s*(?:RETURNING\s+(.*))?$", s)
    if m:
        return _idents(m.group(1), known), [x.strip() for x in (m.group(2) or "").split(",") if x.strip()]
    return _idents(s, known), []


def defuse_info(cfg: CFG):
    known = set(cfg.variables)
    info = {}
    for nid, nd in cfg.nodes.items():
        uses, defs, seen = set(), set(), set()
        if nd.kind == "pred":
            uses = set(_idents(nd.cond, known))
        else:
            for s in nd.stmts:
                u, d = _stmt_defuse(s, known)
                for v in u:
                    if v not in seen:
                        uses.add(v)
                for v in d:
                    defs.add(v)
                    seen.add(v)
        info[nid] = {"uses": uses, "defs": defs, "kind": nd.kind}
    return info


def du_pairs(cfg: CFG):
    """Lista plana de pares DU: {var, def, tipo('c'|'p'), alvo}"""
    info = defuse_info(cfg)
    succ = {n: [] for n in cfg.nodes}
    oute = {n: [] for n in cfg.nodes}
    for s, d, l in cfg.edges:
        succ[s].append(d)
        oute[s].append((s, d, l))
    allv = set()
    for v in info.values():
        allv |= v["uses"] | v["defs"]
    entry_defs = set(cfg.params) | {v for v in allv if "." in v and v != "sqlca.sqlcode"}
    pairs = []
    for var in sorted(allv):
        starts = []
        if var in entry_defs:
            starts.append(("entrada", [cfg.entry]))
        for n, iv in info.items():
            if var in iv["defs"]:
                starts.append((n, list(succ[n])))
        for dlabel, start in starts:
            visited, stack = set(), list(start)
            while stack:
                m = stack.pop()
                if m in visited:
                    continue
                visited.add(m)
                if var in info[m]["uses"]:
                    if info[m]["kind"] == "pred":
                        for (s, d, l) in oute[m]:
                            pairs.append({"var": var, "def": dlabel, "tipo": "p", "alvo": (s, d, l)})
                    else:
                        pairs.append({"var": var, "def": dlabel, "tipo": "c", "alvo": m})
                if var in info[m]["defs"]:
                    continue
                stack.extend(succ[m])
    uniq, seen = [], set()
    for p in pairs:
        key = (p["var"], str(p["def"]), p["tipo"], str(p["alvo"]))
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def pair_covered(trace, pair, info) -> bool:
    var, d, tipo, alvo = pair["var"], pair["def"], pair["tipo"], pair["alvo"]
    starts = [-1] if d == "entrada" else [i for i, n in enumerate(trace) if n == d]
    for i in starts:
        for j in range(i + 1, len(trace)):
            n = trace[j]
            if var in info[n]["uses"]:
                if tipo == "c" and n == alvo:
                    return True
                if tipo == "p" and n == alvo[0] and j + 1 < len(trace) and trace[j + 1] == alvo[1]:
                    return True
            if var in info[n]["defs"]:
                break
    return False


# ---------------------------------------------------------------------------
# 6. Módulo 3b — Teste de Mutação
# ---------------------------------------------------------------------------
_TOK = re.compile(r"(?P<num>\d+(?:\.\d+)?)|(?P<id>[A-Za-z_][\w.]*)|(?P<op><>|<=|>=|[-+*/<>=])|(?P<par>[()])|(?P<ws>\s+)|(?P<other>.)")
_NOT_OPERAND = {"RETURN", "LET", "IF", "THEN", "OR", "AND", "NOT", "IS", "ELSE"}
AOR = {"+": ["-", "*"], "-": ["+"], "*": ["+", "/"], "/": ["*"]}
ROR = {"<": ["<=", ">", ">="], ">": [">=", "<", "<="], "<=": ["<", ">=", ">"],
       ">=": [">", "<=", "<"], "=": ["<>"], "<>": ["="]}
OPERATORS = {"AOR": "Aritmético", "ROR": "Relacional", "COR": "Condicional", "LVR": "Variável local"}


def _spans(line):
    sp = []
    for m in re.finditer(r"(?i)\bIF\b(.*?)\bTHEN\b", line):
        sp.append(("cond", m.start(1), m.end(1)))
    for m in re.finditer(r"(?i)\bWHILE\b(.*)$", line):
        sp.append(("cond", m.start(1), m.end(1)))
    for m in re.finditer(r"(?i)\bLET\s+[\w.]+\s*=\s*(.*?)(?=\bEND\s+IF\b|\bELSE\b|$)", line):
        sp.append(("expr", m.start(1), m.end(1)))
    for m in re.finditer(r"(?i)\bRETURN\b\s*(.*?)(?=\bEND\s+IF\b|\bELSE\b|$)", line):
        sp.append(("expr", m.start(1), m.end(1)))
    return sp


def generate_mutants(func: Func):
    variables = set(func.variables)
    muts, seen = [], set()

    def add(op, li, new_line, desc):
        lines = list(func.lines)
        lines[li] = new_line
        key = "\n".join(lines)
        if key in seen or key == "\n".join(func.lines):
            return
        seen.add(key)
        muts.append({"id": f"M{len(muts) + 1:02d}", "operador": op, "linha": li + 1,
                     "descricao": desc, "lines": lines})

    for li, line in enumerate(func.lines):
        for kind, s, e in _spans(line):
            toks, prev = [], None
            for m in _TOK.finditer(line, s, e):
                if m.lastgroup == "ws":
                    continue
                toks.append((m.lastgroup, m.group(0), m.start(), m.end(), prev))
                prev = (m.lastgroup, m.group(0))
            for g, txt, a, b, pv in toks:
                if g == "op" and txt in AOR:
                    binary = pv and (pv[0] in ("num",) or pv[1] == ")" or
                                     (pv[0] == "id" and pv[1].upper() not in _NOT_OPERAND))
                    if binary:
                        for r in AOR[txt]:
                            add("AOR", li, line[:a] + r + line[b:], f"'{txt}' → '{r}'")
                if g == "op" and kind == "cond" and txt in ROR:
                    for r in ROR[txt]:
                        add("ROR", li, line[:a] + r + line[b:], f"'{txt}' → '{r}'")
                if g == "id" and kind == "cond" and txt.upper() in ("OR", "AND"):
                    r = "AND" if txt.upper() == "OR" else "OR"
                    add("COR", li, line[:a] + r + line[b:], f"'{txt.upper()}' → '{r}'")
                if g == "id" and txt in variables:
                    for r in sorted(variables - {txt}):
                        add("LVR", li, line[:a] + r + line[b:], f"'{txt}' → '{r}'")
    return muts


PROBE = [None, D("-100"), D("-0.01"), D("0"), D("0.01"), D("1"), D("100")]


def _signature(cfg, args, scale):
    try:
        r = run_cfg(cfg, args, scale)
        return ("ok", r["result"])
    except Exception as ex:                           # noqa: BLE001
        return ("err", type(ex).__name__)


def run_mutation(func: Func, cases, scale=2):
    cfg0 = build_cfg(func, True)
    base_sig = [_signature(cfg0, c["args"], scale) for c in cases]
    n = len(func.params)
    probes = list(product(PROBE, repeat=n))
    base_probe = {}
    rows = []
    for m in generate_mutants(func):
        mf = Func(func.name, func.params, m["lines"], func.defines, func.start, func.end, func.types)
        cfg = build_cfg(mf, True)
        killed_by = next((c["id"] for c, b in zip(cases, base_sig)
                          if _signature(cfg, c["args"], scale) != b), None)
        status, witness = "Morto", ""
        if killed_by is None:
            status = "Equivalente (provável)"
            for args in probes:
                if args not in base_probe:
                    base_probe[args] = _signature(cfg0, args, scale)
                if _signature(cfg, args, scale) != base_probe[args]:
                    status = "Vivo"
                    witness = "(" + "; ".join(fmt(a) for a in args) + ")"
                    break
        rows.append({"id": m["id"], "operador": m["operador"], "linha": m["linha"],
                     "mutacao": m["descricao"], "status": status,
                     "morto_por": killed_by or "", "teste_sugerido": witness,
                     "trecho": m["lines"][m["linha"] - 1]})
    return rows


def mutation_score(rows, me_override=None):
    mt = len(rows)
    md = sum(r["status"] == "Morto" for r in rows)
    me = sum(r["status"].startswith("Equivalente") for r in rows) if me_override is None else me_override
    den = mt - me
    return {"Mt": mt, "Md": md, "Me": me, "MS": (md / den * 100) if den > 0 else 100.0}
