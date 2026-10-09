"""
TestingStudio Web — Auditor de Testes de Software

Módulo 1  Caixa-preta  : PCE + AVL com épsilon calculado
Módulo 2  Caixa-branca : GFC + Complexidade Ciclomática de McCabe
Módulo 3  Fluxo de dados (pares Def-Uso) + Teste de Mutação (MS)
"""
import hashlib
import os
from decimal import Decimal as D
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from google import genai

import engine as eg

st.set_page_config(page_title="TestingStudio Web", page_icon="🧪", layout="wide")

# ---------------------------------------------------------------------------
# Visual
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');
:root {
  --ink: #14213D; --muted: #5B6B85; --line: #D9E1EE; --paper: #F7F9FC;
  --ok: #0E7C66; --bad: #B8323F; --warn: #A86A00; --info: #2F5BA8;
}
.stApp, [data-testid="stSidebar"] {
  font-family: 'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
h1, h2, h3, h4 {
  font-family: 'Bricolage Grotesque', 'IBM Plex Sans', system-ui, sans-serif;
  color: var(--ink); letter-spacing: -.01em;
}
code, pre, textarea, [data-testid="stCode"] {
  font-family: 'IBM Plex Mono', ui-monospace, Consolas, monospace !important;
}
textarea {font-size: .86rem !important; line-height: 1.5 !important;}
.block-container {padding-top: 2rem; max-width: 1240px;}
footer {visibility: hidden;}

/* Cabeçalho com a régua de fronteira */
.ts-head {display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
          gap: 20px 40px; background: #fff; border: 1px solid var(--line);
          border-radius: 10px; padding: 22px 28px; margin-bottom: 18px;}
div.ts-head h1 {margin: 0 0 6px 0; padding: 0; font-size: 2.15rem; line-height: 1.1;}
div.ts-head p {margin: 0; color: var(--muted); font-size: .98rem; max-width: 46ch;}
.ts-ruler {position: relative; width: min(380px, 100%); height: 72px; flex: 0 1 380px;}
.ts-track {position: absolute; left: 0; right: 0; top: 6px; height: 30px; display: flex;
           border: 1px solid var(--line); border-radius: 4px; overflow: hidden;}
.ts-inv {flex: 1; background: repeating-linear-gradient(135deg, rgba(184,50,63,.24) 0 5px, rgba(184,50,63,.07) 5px 10px);}
.ts-val {flex: 1; background-color: rgba(14,124,102,.10);
         background-image: linear-gradient(90deg, rgba(14,124,102,.38) 1px, transparent 1px);
         background-size: 10px 100%;}
.ts-mark {position: absolute; top: 0; height: 42px; width: 2px; transform: translateX(-50%);}
.ts-mark span {position: absolute; top: 46px; left: 50%; transform: translateX(-50%);
               font: 500 .8rem 'IBM Plex Mono', ui-monospace, monospace; white-space: nowrap;}
.ts-mark.off {left: 36%; background: var(--bad); color: var(--bad);}
.ts-mark.on  {left: 50%; width: 3px; background: var(--ink); color: var(--ink);}
.ts-mark.in  {left: 64%; background: var(--ok); color: var(--ok);}
.ts-zone {position: absolute; top: 46px; font-size: .74rem; color: var(--muted);}
.ts-zone.l {left: 0;} .ts-zone.r {right: 0;}

/* Avisos */
.note {border-left: 3px solid var(--ok); background: #EAF5F2; padding: 10px 14px;
       border-radius: 6px; color: #0B4F41; margin: 6px 0 14px 0; font-size: .93rem; line-height: 1.5;}
.note.warn {border-color: var(--warn); background: #FBF3E3; color: #5C3A00;}
.note.bad  {border-color: var(--bad);  background: #FBECEE; color: #6E1B24;}
.note.info {border-color: var(--info); background: #EBF0F9; color: #1F3F78;}

/* Métricas, abas, botões, expansores */
[data-testid="stMetric"] {background: #fff; border: 1px solid var(--line); border-radius: 8px;
                          padding: 12px 16px; box-shadow: none;}
[data-testid="stMetricLabel"] {color: var(--muted); font-size: .82rem;}
[data-testid="stMetricValue"] {font-family: 'IBM Plex Mono', ui-monospace, monospace; font-weight: 500; color: var(--ink);}
.stTabs [data-baseweb="tab-list"] {gap: 2px; border-bottom: 1px solid var(--line);}
.stTabs [data-baseweb="tab"] {font-weight: 600; padding: 8px 14px; color: var(--muted);}
.stTabs [aria-selected="true"] {color: var(--ink);}
.stButton > button, .stDownloadButton > button {border-radius: 6px; font-weight: 600;}
[data-testid="stExpander"] {border: 1px solid var(--line); border-radius: 8px; background: #fff;}
section[data-testid="stSidebar"] {border-right: 1px solid var(--line);}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="ts-head">
<div>
<h1>TestingStudio Web</h1>
<p>Auditoria automatizada de testes de software: caixa-preta, caixa-branca, fluxo de dados e mutação.</p>
</div>
<div class="ts-ruler" role="img" aria-label="Régua de fronteira: região inválida à esquerda, região válida à direita, com os pontos X menos épsilon, X e X mais épsilon">
<div class="ts-track"><div class="ts-inv"></div><div class="ts-val"></div></div>
<div class="ts-mark off"><span>X − ε</span></div>
<div class="ts-mark on"><span>X</span></div>
<div class="ts-mark in"><span>X + ε</span></div>
<div class="ts-zone l">inválido</div>
<div class="ts-zone r">válido</div>
</div>
</div>
""",
    unsafe_allow_html=True,
)

def note(texto, tipo=""):
    st.markdown(f'<div class="note {tipo}">{texto}</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Chave da API (Secrets do Streamlit ou campo da barra lateral)
# ---------------------------------------------------------------------------
NOMES_ACEITOS = {"gemini_api_key", "google_api_key", "gemini_key", "api_key"}


def _limpar(valor):
    return str(valor).strip().strip("\"'").strip()


def obter_chave_dos_secrets():
    nomes = []
    try:
        for nome in st.secrets:
            valor = st.secrets[nome]
            nomes.append(str(nome))
            if hasattr(valor, "items"):
                for n2, v2 in valor.items():
                    nomes.append(f"{nome}.{n2}")
                    if str(n2).lower() in NOMES_ACEITOS and _limpar(v2):
                        return _limpar(v2), nomes
            elif str(nome).lower() in NOMES_ACEITOS and _limpar(valor):
                return _limpar(valor), nomes
    except Exception:
        pass
    for env in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if _limpar(os.environ.get(env, "")):
            return _limpar(os.environ[env]), nomes
    return "", nomes


FALLBACK_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash",
                   "gemini-3.5-flash-lite", "gemini-3-flash", "gemini-2.5-flash"]


@st.cache_data(show_spinner=False, ttl=3600)
def listar_modelos(chave: str):
    modelos = []
    try:
        client = genai.Client(api_key=chave)
        for info in client.models.list():
            nome = getattr(info, "name", "")
            acoes = getattr(info, "supported_actions", []) or []
            if "generateContent" in acoes and nome.startswith("models/gemini-"):
                modelos.append(nome.replace("models/", ""))
    except Exception:
        pass
    return modelos


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------
st.sidebar.markdown("### Configuração")
api_key, nomes_secrets = obter_chave_dos_secrets()
if api_key:
    st.sidebar.success("Chave carregada dos Secrets.")
else:
    st.sidebar.warning("Nenhuma chave nos Secrets. Informe abaixo para usar o parecer do Gemini.")
    if nomes_secrets:
        st.sidebar.caption("Secrets detectados (só nomes): " + ", ".join(nomes_secrets))
    api_key = st.sidebar.text_input("Gemini API Key (opcional):", type="password",
                                    help="Só é necessária para o parecer do Gemini. Todo o resto roda sem IA.")

modelos = (listar_modelos(api_key) if api_key.strip() else []) or FALLBACK_MODELS
modelos = list(dict.fromkeys(modelos))
padrao = "gemini-3.6-flash" if "gemini-3.6-flash" in modelos else modelos[0]
modelo = st.sidebar.selectbox("Modelo Gemini:", modelos, index=modelos.index(padrao))

arquivo_up = st.sidebar.file_uploader("Analisar outro fonte (.txt)", type=["txt"],
                                      help="Opcional. Por padrão o app lê cad0001_item_calculo.txt.")

st.sidebar.markdown("---")
st.sidebar.caption("Os cálculos desta ferramenta são determinísticos; o Gemini só gera pareceres opcionais.")

# ---------------------------------------------------------------------------
# Fonte
# ---------------------------------------------------------------------------
if arquivo_up is not None:
    original = arquivo_up.getvalue().decode("utf-8", errors="replace")
    origem = arquivo_up.name
else:
    caminho = Path(__file__).parent / "cad0001_item_calculo.txt"
    try:
        original = caminho.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        st.error("Não encontrei 'cad0001_item_calculo.txt' ao lado do app.py.")
        st.stop()
    origem = caminho.name

h = hashlib.md5(original.encode("utf-8")).hexdigest()
if st.session_state.get("orig_hash") != h:
    st.session_state["orig_hash"] = h
    st.session_state["src"] = original

funcs = []
source = st.session_state["src"]
funcs = eg.split_functions(source)
by_name = {f.name: f for f in funcs}


def _executavel(f):
    return bool(f.params) and eg.is_executable(eg.build_cfg(f, True))


calc = by_name.get("cad0001_calcula_valor") or next((f for f in funcs if _executavel(f)), None)

# ---------------------------------------------------------------------------
# IA opcional
# ---------------------------------------------------------------------------
def parecer_ia(chave_ui, prompt):
    with st.expander("🤖 Parecer do Gemini (parceiro de pareamento)"):
        st.caption("A IA revisa os resultados calculados acima. Ela não substitui o cálculo — confira sempre.")
        if st.button("Pedir parecer", key=f"btn_{chave_ui}"):
            if not api_key.strip():
                st.warning("Informe a Gemini API Key (Secrets ou barra lateral).")
            else:
                with st.spinner(f"Consultando {modelo}..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        st.session_state[f"ia_{chave_ui}"] = client.models.generate_content(
                            model=modelo, contents=prompt).text
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Erro ao chamar a Gemini API ({modelo}): {e}")
                        st.info("Tente outro modelo na barra lateral.")
        if f"ia_{chave_ui}" in st.session_state:
            st.markdown(st.session_state[f"ia_{chave_ui}"])


def df_csv(df):
    return df.to_csv(index=False).encode("utf-8-sig")


def entrada_txt(args):
    return "(" + "; ".join(eg.fmt(a) for a in args) + ")"


def tipo_icon(t):
    return ("🟢 " if t.startswith("Válida") else "🔴 ") + t


# ---------------------------------------------------------------------------
# Dados do Módulo 1 (usados em várias abas)
# ---------------------------------------------------------------------------
suite, resultados, cfg_calc, ei, rule, rules, pce_rows = None, None, None, None, None, None, None
if calc:
    prec, escala = eg.detect_decimal(calc, source)
    ei = eg.epsilon_info(prec, escala)
    rules = eg.derive_rules(calc, ei["epsilon"])
    rule = rules[0]
    pce_rows = eg.build_pce(calc, rule)
    cfg_calc = eg.build_cfg(calc, True)
    if len(calc.params) == 3 and eg.is_executable(cfg_calc):
        suite = eg.build_suite(rule, ei["epsilon"], 3)
        resultados = eg.run_suite(cfg_calc, suite, escala)

tabs = st.tabs([
    "Fonte",
    "Módulo 1: Caixa-preta",
    "Módulo 2: Caixa-branca",
    "Módulo 3: Fluxo de dados",
    "Módulo 3: Mutação",
])

# ===========================================================================
# ABA 0 — Fonte
# ===========================================================================
with tabs[0]:
    st.subheader("Código-fonte analisado")
    st.caption(f"Arquivo: **{origem}** · o texto abaixo é editável — todas as abas analisam o que está na caixa. "
               "Experimente remover a validação de negativos e veja os testes falharem.")
    st.text_area("Fonte (Informix-4GL)", key="src", height=380, label_visibility="collapsed")
    st.button("↺ Restaurar arquivo original", on_click=lambda: st.session_state.update(src=original))

    if not funcs:
        st.error("Nenhuma função (FUNCTION ... END FUNCTION) encontrada no fonte.")
        st.stop()

# ===========================================================================
# ABA 1 — Módulo 1: Caixa-preta
# ===========================================================================
with tabs[1]:
    st.subheader("Módulo 1: Teste funcional (caixa-preta): PCE e AVL")
    if not calc:
        note("Nenhuma função de cálculo executável encontrada para a análise de caixa-preta.", "warn")
    else:
        st.caption(f"Unidade sob teste: `{calc.name}({', '.join(calc.params)})`")
        sub = st.tabs(["Relatório (PCE & AVL)", "Gráfico de Fronteira",
                       "Execução com oráculo", "Parecer do Gemini"])

        # -- Relatório -------------------------------------------------------
        with sub[0]:
            st.markdown("#### Épsilon (ε) calculado a partir do tipo de dado")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tipo", f"DECIMAL({ei['precision']},{ei['scale']})")
            c2.metric("Épsilon ε", eg.fmt(ei["epsilon"]))
            c3.metric("Fórmula", f"10^-{ei['scale']}")
            c4.metric("Máximo do tipo", f"{ei['max']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            note(
                f"<b>Por que ε = {eg.fmt(ei['epsilon'])}?</b> O dado tem {ei['scale']} casas decimais, então a menor "
                f"variação fisicamente representável é 10<sup>-{ei['scale']}</sup> = {eg.fmt(ei['epsilon'])} (1 centavo). "
                "Um passo menor seria arredondado para o mesmo valor e não criaria um ponto de teste distinto; "
                "um passo maior poderia saltar sobre o defeito de fronteira (operadores &lt; vs &lt;=).",
                "info",
            )
            if not rule["from_code"]:
                note("<b>Atenção:</b> o código analisado <b>não contém a validação de valores negativos</b> esperada na "
                     "especificação. A AVL abaixo usa a regra da especificação (fronteira em 0,00), mas a execução dos testes mostrará "
                     "as falhas correspondentes.", "bad")

            st.markdown("#### Particionamento em Classes de Equivalência (PCE)")
            df_pce = pd.DataFrame(pce_rows)
            df_pce["Tipo"] = df_pce["Tipo"].map(tipo_icon)
            st.dataframe(df_pce, hide_index=True)
            if any(r["Tipo"].startswith("Válida (tratada") for r in pce_rows):
                note("<b>Divergência especificação × código:</b> a especificação lista valores nulos entre as classes inválidas, mas o "
                     "código converte <code>NULL</code> em 0 antes de validar. Esta ferramenta segue o comportamento do "
                     "código (nulo = válido). Confirme qual é a regra desejada.", "warn")

            st.markdown("#### Análise do Valor Limite (AVL)")
            avl_rows = []
            for r in rules:
                cond = f"{' / '.join(r['vars']) or 'x'} {r['op']} {eg.fmt(r['c'])}"
                just = {
                    "On": "Exatamente sobre a fronteira.",
                    "Off": f"Primeiro valor do outro lado da fronteira (passo de ε = {eg.fmt(ei['epsilon'])}).",
                    "Interior": "Profundamente dentro da região válida.",
                    "Exterior": "Profundamente dentro da região inválida.",
                }
                for p in r["points"]:
                    avl_rows.append({"Entrada": "val_param1..3" if len(calc.params) == 3 else "parâmetros",
                                     "Ponto": p["ponto"], "Valor de teste": eg.fmt(p["valor"]),
                                     "Fronteira (inválido se)": cond,
                                     "Classe": ("🟢 " if p["classe"] == "Válida" else "🔴 ") + p["classe"],
                                     "Resultado esperado": p["esperado"], "Justificativa": just[p["ponto"]]})
            st.dataframe(pd.DataFrame(avl_rows), hide_index=True)

            if suite:
                st.markdown("#### Casos de teste derivados")
                df_ct = pd.DataFrame([{"ID": c["id"], "Técnica": c["tecnica"], "Descrição": c["descricao"],
                                       "Entrada": entrada_txt(c["args"]), "Resultado esperado": eg.fmt(c["esperado"])}
                                      for c in suite])
                st.dataframe(df_ct, hide_index=True)
                st.download_button("⬇️ Baixar casos de teste (CSV)", df_csv(df_ct), "casos_de_teste.csv", "text/csv")
                st.caption("O resultado esperado vem de um **oráculo externo** (regra de negócio da especificação), "
                           "nunca do próprio código-fonte.")

        # -- Gráfico ---------------------------------------------------------
        with sub[1]:
            st.markdown("#### Pontos de fronteira (AVL)")
            pts = pd.DataFrame([{"Ponto": p["ponto"], "Valor": float(p["valor"]), "Classe": p["classe"],
                                 "Rótulo": f"{p['ponto']} ({eg.fmt(p['valor'])})", "Esperado": p["esperado"]}
                                for p in rule["points"]])
            ordem = list(pts.sort_values("Valor")["Ponto"])
            base = alt.Chart(pts)
            linha = alt.Chart(pd.DataFrame({"x": [float(rule["c"])]})).mark_rule(
                strokeDash=[6, 4], color="#14213D", size=2).encode(x="x:Q")
            bolas = base.mark_circle(size=320).encode(
                x=alt.X("Valor:Q", title="Valor de entrada"),
                y=alt.Y("Ponto:N", sort=ordem, title=None),
                color=alt.Color("Classe:N", scale=alt.Scale(domain=["Válida", "Inválida"],
                                                            range=["#0E7C66", "#B8323F"])),
                tooltip=["Ponto", "Valor", "Classe", "Esperado"])
            textos = base.mark_text(dy=-20, fontSize=12, color="#14213D").encode(
                x="Valor:Q", y=alt.Y("Ponto:N", sort=ordem), text="Rótulo:N")
            st.altair_chart((linha + bolas + textos).properties(height=260, width="container")
                            .configure_view(stroke=None)
                            .configure_axis(gridColor="#E6ECF5", domainColor="#B8C4D9", tickColor="#B8C4D9",
                                            labelColor="#5B6B85", titleColor="#5B6B85", labelFontSize=12)
                            .configure_legend(labelColor="#5B6B85", titleColor="#5B6B85"))
            st.caption("Linha tracejada = fronteira. Verde = região válida · vermelho = região inválida.")
            tab = pts[["Ponto", "Valor", "Classe", "Esperado"]].copy()
            tab["Valor"] = tab["Valor"].map(lambda v: eg.fmt(D(str(v))))
            st.dataframe(tab, hide_index=True)

        # -- Execução --------------------------------------------------------
        with sub[2]:
            if not resultados:
                note("A unidade não é executável pelo interpretador interno (usa SQL, CALL ou outros comandos).", "warn")
            else:
                ok = sum(r["ok"] for r in resultados)
                c1, c2, c3 = st.columns(3)
                c1.metric("Casos executados", len(resultados))
                c2.metric("Passaram ✅", ok)
                c3.metric("Falharam ❌", len(resultados) - ok)
                if ok == len(resultados):
                    note("Todos os casos de teste passaram: o código respeita o oráculo.")
                else:
                    note("Há falhas — os casos que não passam revelam onde o código diverge da regra de negócio "
                         "(ex.: ausência da validação de valores negativos).", "bad")
                df_ex = pd.DataFrame([{
                    "ID": r["id"], "Técnica": r["tecnica"], "Entrada": entrada_txt(r["args"]),
                    "Esperado (oráculo)": eg.fmt(r["esperado"]),
                    "Obtido": eg.fmt(r["obtido"]) if not r["erro"] else r["erro"],
                    "Resultado": "✅ passou" if r["ok"] else "❌ falhou",
                    "Caminho no GFC": " → ".join(f"N{n}" for n in r["trace"])} for r in resultados])
                st.dataframe(df_ex, hide_index=True)

                cn = {n for r in resultados for n in r["trace"]}
                ce = {e for r in resultados for e in r["edges"]}
                total_arestas = len(cfg_calc.edges)
                st.markdown("**Cobertura estrutural da suíte caixa-preta** (todos-nós e todas-arestas)")
                k1, k2 = st.columns(2)
                k1.metric("Todos-nós", f"{len(cn)}/{len(cfg_calc.nodes)}",
                          f"{len(cn) / len(cfg_calc.nodes) * 100:.0f}%")
                k2.metric("Todas-arestas", f"{len(ce)}/{total_arestas}",
                          f"{len(ce) / total_arestas * 100:.0f}%")

                st.markdown("**Oráculos de asserção:** a suíte como código executável")
                linhas_as = ["from decimal import Decimal as D", "", "# oráculo = regra de negócio externa, não o código-fonte"]
                for c in suite:
                    args = ", ".join("None" if a is None else f"D('{a}')" for a in c["args"])
                    linhas_as.append(f"assert cad0001_calcula_valor({args}) == D('{c['esperado']}'), \"{c['id']}: {c['descricao']}\"")
                st.code("\n".join(linhas_as), language="python")

        # -- IA --------------------------------------------------------------
        with sub[3]:
            ctx = (f"Épsilon calculado: {ei['epsilon']} (DECIMAL({ei['precision']},{ei['scale']})).\n"
                   f"Fronteiras encontradas no código: {[(r['op'], str(r['c']), r['vars']) for r in rules]} "
                   f"(derivadas do código: {rule['from_code']}).\n"
                   "PCE:\n" + pd.DataFrame(pce_rows).to_csv(index=False))
            if resultados:
                ctx += "\nResultado da execução da suíte:\n" + "\n".join(
                    f"{r['id']} {entrada_txt(r['args'])} esperado={eg.fmt(r['esperado'])} obtido={eg.fmt(r['obtido'])} ok={r['ok']}"
                    for r in resultados)
            parecer_ia("m1", f"""Você é um analista de testes de software. Revise a análise de caixa-preta (PCE + AVL)
abaixo, calculada por uma ferramenta determinística. Aponte lacunas, divergências entre a especificação e o código
e classes ou valores-limite que faltam. Não invente regras que não estejam no código. Responda em português,
com tabelas quando útil.

Código-fonte:
{source}

Resultados calculados:
{ctx}""")

# ===========================================================================
# ABA 2 — Módulo 2: Caixa-branca (GFC + McCabe)
# ===========================================================================
with tabs[2]:
    st.subheader("Módulo 2: Teste estrutural (caixa-branca): GFC e Complexidade Ciclomática")
    st.caption("Do código ao grafo de fluxo de controle e à complexidade ciclomática de McCabe.")
    nomes_f = [f.name for f in funcs]
    idx_def = nomes_f.index(calc.name) if calc and calc.name in nomes_f else 0
    cA, cB = st.columns([3, 2])
    fn_sel = cA.selectbox("Função", nomes_f, index=idx_def, key="wb_fn")
    decomp = cB.checkbox("Decompor condições compostas (OR/AND)", value=True,
                         help="Cada condição simples vira um nó predicativo "
                              "Desmarque para contar a condição composta como um único predicado.")
    fsel = by_name[fn_sel]
    cfg = eg.build_cfg(fsel, decomp)
    mc = eg.mccabe(cfg)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Nós (N)", mc["N"])
    c2.metric("Arestas (E)", mc["E"])
    c3.metric("Predicados (P)", mc["P"])
    c4.metric("Regiões (R)", mc["R"] if mc["R"] is not None else "—")
    c5.metric("V(G)", mc["V_EN"])

    if mc["consistente"]:
        note(f"As <b>três fórmulas equivalentes de McCabe</b> resultam no mesmo valor: <b>V(G) = {mc['V_EN']}</b> "
             f"— {eg.complexity_level(mc['V_EN'])}.")
    else:
        note("As três fórmulas divergiram — verifique se o fonte tem estruturas fora do subconjunto suportado "
             "(GOTO, CASE, EXIT WHILE...).", "warn")

    st.markdown("**As 3 fórmulas**")
    st.dataframe(pd.DataFrame([
        {"Método": "1 · Topológico", "Fórmula": "V(G) = E − N + 2", "Cálculo": f"{mc['E']} − {mc['N']} + 2", "Resultado": mc["V_EN"]},
        {"Método": "2 · Lógico", "Fórmula": "V(G) = P + 1", "Cálculo": f"{mc['P']} + 1", "Resultado": mc["V_P"]},
        {"Método": "3 · Espacial", "Fórmula": "V(G) = R", "Cálculo": f"{mc['R']} regiões (1 externa)", "Resultado": mc["V_R"] if mc["R"] is not None else "—"},
    ]), hide_index=True)

    cob_n = cob_e = None
    if fn_sel == (calc.name if calc else None) and resultados and decomp:
        if st.checkbox("Colorir o GFC com a cobertura da suíte caixa-preta", value=False):
            cob_n = {n for r in resultados for n in r["trace"]}
            cob_e = {e for r in resultados for e in r["edges"]}
    st.markdown("**Grafo de Fluxo de Controle**")
    st.graphviz_chart(eg.to_dot(cfg, cob_n, cob_e))
    st.caption("◇ nó predicativo · ▭ bloco de comandos · verde = ramo Verdadeiro (V) · vermelho = ramo Falso (F)")

    st.markdown("**Derivação dos casos de teste**")
    caminhos, total_caminhos = eg.basis_paths(cfg, mc["V_EN"])
    note(f"V(G) = <b>{mc['V_EN']}</b> ⇒ são necessários, no mínimo, <b>{mc['V_EN']} casos de teste</b> independentes "
         f"para cobrir o conjunto básico de caminhos. Testar menos que V(G) deixa caminhos cegos. "
         f"({total_caminhos} caminhos entrada→saída encontrados; o conjunto básico escolhido tem {len(caminhos)}.)", "info")
    st.dataframe(pd.DataFrame([{"Caminho básico": f"CB{i + 1}",
                                "Sequência de nós": " → ".join(f"N{n}" for n in eg.path_nodes(cfg, p)),
                                "Arestas": len(p)} for i, p in enumerate(caminhos)]), hide_index=True)
    if fn_sel == (calc.name if calc else None) and resultados:
        st.caption(f"A suíte caixa-preta tem {len(resultados)} casos (≥ V(G) = {mc['V_EN']}).")

    with st.expander("Nós do grafo"):
        st.dataframe(pd.DataFrame([{"Nó": f"N{n.id}", "Tipo": {"block": "Bloco", "pred": "Predicado", "exit": "Saída"}[n.kind],
                                    "Conteúdo": n.cond if n.kind == "pred" else " ; ".join(n.stmts) or "—"}
                                   for n in cfg.nodes.values()]), hide_index=True)

    parecer_ia("m2", f"""Você é um especialista em teste de software. Valide o cálculo da Complexidade Ciclomática de
McCabe da função `{fn_sel}` feito por uma ferramenta determinística: N={mc['N']}, E={mc['E']}, P={mc['P']},
R={mc['R']}, V(G)={mc['V_EN']} (decomposição de condições compostas: {decomp}). Confira a contagem a partir do
código, explique o que V(G) significa para o esforço de teste e sugira riscos. Responda em português.

Código:
{source}""")

# ===========================================================================
# ABA 3 — Módulo 3: Fluxo de dados
# ===========================================================================
with tabs[3]:
    st.subheader("Módulo 3: Teste de fluxo de dados: pares Definição-Uso")
    st.caption("d (definição), c-uso (uso computacional, associado a nó) e p-uso (uso predicativo, associado a aresta).")
    fn_du = st.selectbox("Função", nomes_f, index=idx_def, key="du_fn")
    cfg_du = eg.build_cfg(by_name[fn_du], True)
    pares = eg.du_pairs(cfg_du)
    info_du = eg.defuse_info(cfg_du)

    cobertos = None
    if fn_du == (calc.name if calc else None) and resultados:
        trs = [r["trace"] for r in resultados]
        cobertos = [any(eg.pair_covered(t, p, info_du) for t in trs) for p in pares]

    if not pares:
        note("Nenhum par definição-uso encontrado nesta função.", "warn")
    else:
        grupos = {}
        for i, p in enumerate(pares):
            grupos.setdefault((p["var"], str(p["def"])), []).append((i, p))
        linhas = []
        for (var, d), lst in grupos.items():
            cs = sorted({f"N{p['alvo']}" for _i, p in lst if p["tipo"] == "c"})
            ps = [f"(N{p['alvo'][0]}→N{p['alvo'][1]})" for _i, p in lst if p["tipo"] == "p"]
            lin = {"Variável": var, "Nó Def (d)": "entrada" if d == "entrada" else f"N{d}",
                   "Nós c-uso": ", ".join(cs) or "—", "Arestas p-uso": ", ".join(ps) or "—"}
            if cobertos is not None:
                lin["Cobertos pela suíte"] = f"{sum(cobertos[i] for i, _p in lst)}/{len(lst)}"
            linhas.append(lin)
        st.markdown("**Tabela de pares DU**")
        st.dataframe(pd.DataFrame(linhas), hide_index=True)
        st.caption("“entrada” = valor recebido como parâmetro ou variável global (definido fora da função).")

        defs_unicas = {(p["var"], str(p["def"])) for p in pares}
        n_c = sum(p["tipo"] == "c" for p in pares)
        n_p = sum(p["tipo"] == "p" for p in pares)
        st.markdown("**Critérios de Rapps e Weyuker — elementos requeridos**")
        k = st.columns(4)
        if cobertos is None:
            k[0].metric("Todas-definições", len(defs_unicas))
            k[1].metric("Todos-c-usos", n_c)
            k[2].metric("Todos-p-usos", n_p)
            k[3].metric("Todos-usos", len(pares))
        else:
            cd = sum(any(cobertos[i] for i, _p in lst) for lst in grupos.values())
            cc = sum(c for c, p in zip(cobertos, pares) if p["tipo"] == "c")
            cp = sum(c for c, p in zip(cobertos, pares) if p["tipo"] == "p")
            k[0].metric("Todas-definições", f"{cd}/{len(defs_unicas)}")
            k[1].metric("Todos-c-usos", f"{cc}/{n_c}")
            k[2].metric("Todos-p-usos", f"{cp}/{n_p}")
            k[3].metric("Todos-usos", f"{sum(cobertos)}/{len(pares)}")
            st.caption("Cobertura medida executando a suíte caixa-preta do Módulo 1 sobre o GFC.")
            faltam = [p for c, p in zip(cobertos, pares) if not c]
            if faltam:
                note("Pares não cobertos podem ser <b>infactíveis</b>: nenhum dado de entrada exercita aquele caminho. "
                     "Exemplo: se a variável foi definida como 0 (tratamento de nulo), o p-uso <code>var &lt; 0</code> "
                     "nunca resulta em Verdadeiro a partir dessa definição.", "warn")
                st.dataframe(pd.DataFrame([{
                    "Variável": p["var"], "Def": "entrada" if p["def"] == "entrada" else f"N{p['def']}",
                    "Uso": (f"c-uso N{p['alvo']}" if p["tipo"] == "c" else f"p-uso (N{p['alvo'][0]}→N{p['alvo'][1]}, {p['alvo'][2]})")}
                    for p in faltam]), hide_index=True)
            else:
                note("A suíte cobre todos os pares definição-uso (critério Todos-usos).")
        st.markdown("**Hierarquia:** *Todos-usos* ⊇ *Todos-c-usos/alguns-p-usos* e *Todos-p-usos/alguns-c-usos* ⊇ *Todos-p-usos* ⊇ *Todas-arestas*.")

    parecer_ia("m3a", f"""Você é um especialista em teste de software. Revise os pares definição-uso (DU) da função
`{fn_du}` calculados por uma ferramenta determinística. Indique pares que parecem infactíveis, variáveis sem
uso (anomalias de fluxo de dados) e casos de teste que cobririam os pares restantes. Responda em português.

Pares (var, def, tipo, alvo):
{[(p['var'], p['def'], p['tipo'], p['alvo']) for p in pares]}

Código:
{source}""")

# ===========================================================================
# ABA 4 — Módulo 3: Mutação
# ===========================================================================
@st.cache_data(show_spinner="Gerando e executando mutantes...")
def mutacao_cached(fonte: str, fname: str, ids: tuple):
    fs = {f.name: f for f in eg.split_functions(fonte)}
    f = fs[fname]
    pr, sc = eg.detect_decimal(f, fonte)
    e = eg.epsilon_info(pr, sc)
    r = eg.derive_rules(f, e["epsilon"])[0]
    su = [c for c in eg.build_suite(r, e["epsilon"], 3) if c["id"] in ids]
    return eg.run_mutation(f, su, sc)


with tabs[4]:
    st.subheader("Módulo 3: Teste de mutação: quão boa é a sua suíte de testes?")
    st.caption("Injetamos defeitos propositais (mutantes) e verificamos se os testes “matam” cada um.")
    if not (calc and suite):
        note("A mutação requer uma função executável com 3 parâmetros (como `cad0001_calcula_valor`).", "warn")
    else:
        modo = st.radio("Suíte de testes usada contra os mutantes",
                        ["Completa (PCE + AVL)", "Somente PCE", "Somente AVL", "Somente o caminho feliz", "Personalizada"],
                        horizontal=True)
        todos = [c["id"] for c in suite]
        if modo.startswith("Completa"):
            ids = todos
        elif modo == "Somente PCE":
            ids = [c["id"] for c in suite if c["tecnica"] == "PCE"]
        elif modo == "Somente AVL":
            ids = [c["id"] for c in suite if c["tecnica"] == "AVL"]
        elif modo == "Somente o caminho feliz":
            ids = [todos[0]]
        else:
            ids = st.multiselect("Casos de teste", todos, default=todos)
        if not ids:
            note("Selecione ao menos um caso de teste.", "warn")
        else:
            rows = mutacao_cached(source, calc.name, tuple(ids))
            man = st.checkbox("Informar Me (mutantes equivalentes) manualmente", value=False)
            me_val = None
            if man:
                me_val = st.number_input("Me", min_value=0, max_value=len(rows), value=0, step=1)
            sc = eg.mutation_score(rows, me_val)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Mutantes gerados (Mt)", sc["Mt"])
            c2.metric("Mortos (Md)", sc["Md"])
            c3.metric("Equivalentes (Me)", sc["Me"])
            c4.metric("Escore de Mutação (MS)", f"{sc['MS']:.1f}%")
            st.markdown(f"`MS = Md / (Mt − Me) × 100 = {sc['Md']} / ({sc['Mt']} − {sc['Me']}) × 100 = {sc['MS']:.1f}%`")
            if sc["MS"] >= 90:
                note("MS alto: a suíte detecta a maioria dos defeitos simulados.")
            elif sc["MS"] >= 70:
                note("MS intermediário: há mutantes sobrevivendo — veja os testes sugeridos abaixo.", "warn")
            else:
                note("MS baixo: muitos mutantes sobreviveram. A suíte não é capaz de detectar falhas reais.", "bad")

            df_m = pd.DataFrame(rows)
            resumo = df_m.groupby("operador")["status"].value_counts().unstack(fill_value=0)
            resumo = resumo.reindex(columns=["Morto", "Vivo", "Equivalente (provável)"], fill_value=0)
            resumo.insert(0, "Descrição", [eg.OPERATORS[o] for o in resumo.index])
            resumo.insert(1, "Total", resumo[["Morto", "Vivo", "Equivalente (provável)"]].sum(axis=1))
            st.markdown("**Por operador de mutação**")
            st.dataframe(resumo.reset_index().rename(columns={"operador": "Operador"}), hide_index=True)

            filtro = st.selectbox("Mostrar mutantes", ["Todos", "Vivo", "Morto", "Equivalente (provável)"])
            ic = {"Morto": "💀 Morto", "Vivo": "🧟 Vivo", "Equivalente (provável)": "🟰 Equivalente (provável)"}
            vis = df_m if filtro == "Todos" else df_m[df_m["status"] == filtro]
            st.dataframe(pd.DataFrame({
                "ID": vis["id"], "Operador": vis["operador"], "Mutação": vis["mutacao"],
                "Código mutante": vis["trecho"], "Status": vis["status"].map(ic),
                "Morto por": vis["morto_por"], "Entrada que mataria": vis["teste_sugerido"]}), hide_index=True)
            st.download_button("⬇️ Baixar mutantes (CSV)", df_csv(df_m), "mutantes.csv", "text/csv")

            vivos = df_m[df_m["status"] == "Vivo"]
            if len(vivos):
                note(f"<b>{len(vivos)} mutantes vivos.</b> Cada um tem uma entrada que o mataria (coluna "
                     "“Entrada que mataria”). Adicione essas entradas à suíte para elevar o MS.", "warn")
            st.caption("“Equivalente (provável)” = nenhuma entrada de uma grade de sondagem (NULL, negativos, 0, ±ε, 1, 100) "
                       "distingue o mutante do original — é uma heurística; confirme manualmente. "
                       "Mutantes que lançam erro de execução contam como mortos.")

    parecer_ia("m3b", f"""Você é um especialista em teste de software. Avalie o resultado do teste de mutação da função
`{calc.name if calc else '-'}`. Explique quais mutantes sobreviveram, se algum parece equivalente e que casos de
teste adicionais elevariam o Escore de Mutação. Responda em português.

Código:
{source}""")

st.divider()
st.caption("TestingStudio Web")
