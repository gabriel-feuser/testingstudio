"""
TestingStudio Web — Auditor de Testes de Software

Módulo 1  Caixa-preta  : PCE + AVL com épsilon calculado
Módulo 2  Caixa-branca : GFC + Complexidade Ciclomática de McCabe
Módulo 3  Fluxo de dados (pares Def-Uso) + Teste de Mutação (MS)
Módulo 4  Validação dos resultados
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
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=Instrument+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
/* Cores que acompanham o tema ativo do Streamlit (claro ou escuro): o Streamlit
   define color-scheme em .stApp e light-dark() escolhe o valor certo. */
:root {
  --bg: light-dark(#F2F2F7, #0C0C11);
  --surface: light-dark(#FFFFFF, #15151C);
  --side: light-dark(#E6E6EF, #101016);
  --ink: light-dark(#14141B, #EDEDF4);
  --line: light-dark(rgba(20,20,27,.24), rgba(237,237,244,.20));
  --line-strong: light-dark(#14141B, #4A4A5C);
  --accent: light-dark(#D9480F, #FF8A4C);
  --on-accent: light-dark(#FFFFFF, #1A0E06);
  --ok: light-dark(#0B7A4F, #3DDC97); --bad: light-dark(#C0183F, #FF6B8B);
  --warn: light-dark(#8F5600, #FFC857); --info: light-dark(#2253B8, #86B4FF);
  --ok-bg: light-dark(#E3F4EC, rgba(61,220,151,.12));
  --bad-bg: light-dark(#FBE7EC, rgba(255,107,139,.12));
  --warn-bg: light-dark(#FBF0DB, rgba(255,200,87,.12));
  --info-bg: light-dark(#E6EEFB, rgba(134,180,255,.12));
}
@supports not (color: light-dark(#000, #fff)) {
  :root {
    --bg: #F2F2F7; --surface: #FFFFFF; --side: #E6E6EF; --ink: #14141B; --line: rgba(20,20,27,.24);
    --line-strong: #14141B; --accent: #D9480F; --on-accent: #FFFFFF;
    --ok: #0B7A4F; --bad: #C0183F; --warn: #8F5600; --info: #2253B8;
    --ok-bg: #E3F4EC; --bad-bg: #FBE7EC; --warn-bg: #FBF0DB; --info-bg: #E6EEFB;
  }
}
.stApp {background: var(--bg);}
[data-testid="stHeader"] {background: transparent;}
.stApp, [data-testid="stSidebar"] {
  font-family: 'Instrument Sans', system-ui, -apple-system, 'Segoe UI', sans-serif;
}
h1, h2, h3 {
  font-family: 'Syne', 'Trebuchet MS', system-ui, sans-serif;
  color: inherit; letter-spacing: -.015em; font-weight: 700;
}
h4 {font-family: 'Instrument Sans', system-ui, sans-serif; color: inherit; font-weight: 700; letter-spacing: -.005em;}
code, pre, textarea, [data-testid="stCode"] {
  font-family: 'JetBrains Mono', ui-monospace, Consolas, monospace !important;
}
textarea {font-size: .84rem !important; line-height: 1.5 !important;}
.block-container {padding-top: 5rem !important; max-width: 1240px;}
footer {visibility: hidden;}

/* Cabeçalho: bloco escuro com o degrau da fronteira */
.ts-head {--h-ok: #3DDC97; --h-bad: #FF6B8B; --h-fg: #F2F2F7;
          display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between;
          gap: 24px 48px; background: #14141B; color: var(--h-fg);
          border: 1.5px solid var(--line-strong); border-left: 8px solid var(--accent); border-radius: 2px;
          padding: 26px 30px 30px; margin-bottom: 24px; box-shadow: 5px 5px 0 var(--accent);}
div.ts-head h1 {margin: 0 0 8px 0; padding: 0; font-size: 2.5rem; line-height: 1.05; font-weight: 800; color: var(--h-fg);}
div.ts-head p {margin: 0; color: #B7B7CA; font-size: .98rem; max-width: 44ch;}
.ts-step {position: relative; width: min(400px, 100%); flex: 0 1 400px; padding-bottom: 34px;}
.ts-bars {display: flex; align-items: flex-end; gap: 5px; height: 58px;}
.ts-bars .b {display: block; flex: 1; position: relative; border-radius: 1px; font-style: normal;}
.ts-bars .b.inv {height: 30%; background: var(--h-bad); opacity: .55;}
.ts-bars .b.val {height: 86%; background: var(--h-ok); opacity: .85;}
.ts-bars .b.mk {opacity: 1;}
.ts-bars .b.mk.on {height: 100%; background: var(--h-fg);}
.ts-bars .b.mk em {position: absolute; top: calc(100% + 9px); left: 50%; transform: translateX(-50%);
                   font: 500 .78rem 'JetBrains Mono', ui-monospace, monospace; font-style: normal;
                   white-space: nowrap; color: var(--h-fg);}
.ts-bars .b.mk.off em {color: var(--h-bad);}
.ts-bars .b.mk.in em {color: var(--h-ok);}
.ts-cap {position: absolute; bottom: 0; font-size: .72rem; color: #9A9AB0;}
.ts-cap.l {left: 0;} .ts-cap.r {right: 0;}

/* Avisos */
.note {border: 1.5px solid var(--ok); background: var(--ok-bg); padding: 10px 14px;
       border-radius: 2px; color: inherit; margin: 6px 0 14px 0; font-size: .93rem; line-height: 1.5;}
.note.warn {border-color: var(--warn); background: var(--warn-bg);}
.note.bad  {border-color: var(--bad);  background: var(--bad-bg);}
.note.info {border-color: var(--info); background: var(--info-bg);}

/* Métricas, abas, botões, campos, tabelas, expansores */
[data-testid="stMetric"] {background: var(--surface); border: 1.5px solid var(--line); border-left: 6px solid var(--accent);
                          border-radius: 2px; padding: 12px 16px; box-shadow: none;}
[data-testid="stMetricLabel"] {opacity: .75;}
[data-testid="stMetricLabel"] p {text-transform: uppercase; letter-spacing: .05em; font-size: .72rem;}
[data-testid="stMetricValue"] {font-family: 'JetBrains Mono', ui-monospace, monospace; font-weight: 500; color: inherit;
                               font-size: clamp(.9rem, 1.15vw, 1.3rem);}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div {white-space: normal !important;
                               overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere;}
.stTabs [role="tablist"] {gap: 4px !important; row-gap: 6px !important; border-bottom: none !important;
                           box-shadow: none !important; background: transparent !important;
                           flex-wrap: wrap !important; overflow: visible !important;}
.stTabs [class*="SelectionIndicator"] {display: none !important;}
.stTabs [role="tablist"]::before, .stTabs [role="tablist"]::after {display: none !important;}
.stTabs [role="tab"] {height: auto !important; padding: 6px 10px !important;
    border: 1.5px solid var(--line) !important; border-radius: 2px !important; background: transparent !important;
    opacity: 1 !important; margin: 0 !important; box-shadow: none !important;}
.stTabs [role="tab"]::before, .stTabs [role="tab"]::after {display: none !important; background: transparent !important;
    border-color: transparent !important; height: 0 !important;}
.stTabs [role="tab"] p {color: inherit !important; font-weight: 600 !important; font-size: .86rem !important;}
.stTabs [role="tab"][aria-selected="true"] {background: var(--ink) !important; border-color: var(--ink) !important;}
.stTabs [role="tab"][aria-selected="true"] p {color: var(--bg) !important;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display: none !important;}
.stButton > button, .stDownloadButton > button {border-radius: 2px; font-weight: 600; border: 1.5px solid var(--line-strong);}
[data-testid="stBaseButton-primary"], button[kind="primary"] {background: var(--accent) !important;
    border-color: var(--accent) !important; color: var(--on-accent) !important;}
[data-testid="stBaseButton-primary"] p, button[kind="primary"] p {color: inherit !important;}
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {border-radius: 2px !important;}
[data-testid="stAlert"] {border-radius: 2px;}
[data-testid="stDataFrame"] {border: 1.5px solid var(--line-strong); border-radius: 2px; overflow: hidden;}
[data-testid="stExpander"] {border: 1.5px solid var(--line-strong); border-radius: 2px; background: transparent;}
[data-testid="stExpander"] details, [data-testid="stExpander"] summary {background: transparent;}
section[data-testid="stSidebar"], [data-testid="stSidebarContent"] {background: var(--side);}
section[data-testid="stSidebar"] {border-right: 1.5px solid var(--line-strong);}
</style>
""",
    unsafe_allow_html=True,
)


def _barras_degrau():
    marcas = {7: ("off", "X − ε"), 11: ("on", "X"), 15: ("in", "X + ε")}
    out = []
    for i in range(22):
        lado = "inv" if i < 11 else "val"
        if i in marcas:
            cls, rot = marcas[i]
            out.append(f'<i class="b {lado} mk {cls}"><em>{rot}</em></i>')
        else:
            out.append(f'<i class="b {lado}"></i>')
    return "".join(out)


st.markdown(
    f"""
<div class="ts-head">
<div>
<h1>TestingStudio Web</h1>
<p>Auditoria automatizada de testes de software: caixa-preta, caixa-branca, fluxo de dados e mutação.</p>
</div>
<div class="ts-step" role="img" aria-label="Degrau de fronteira: região inválida à esquerda, região válida à direita, com os pontos X menos épsilon, X e X mais épsilon">
<div class="ts-bars">{_barras_degrau()}</div>
<span class="ts-cap l">inválido</span><span class="ts-cap r">válido</span>
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

arquivo_up = st.sidebar.file_uploader("Analisar outro fonte (.txt, .4gl)", type=["txt", "4gl", "src", "prg"],
                                      help="Envie o fonte que deseja testar. Sem envio, o app lê cad0001_item_calculo.txt.")
slot_unit = st.sidebar.container()

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


candidatas = [f for f in funcs if f.params]
calc = None
if candidatas:
    nomes_c = [f.name for f in candidatas]
    padrao_c = (next((n for n in nomes_c if n == "cad0001_calcula_valor"), None)
                or next((f.name for f in candidatas if eg.is_testable(f)), nomes_c[0]))
    escolhida = slot_unit.selectbox("Unidade sob teste (Módulo 1)", nomes_c, index=nomes_c.index(padrao_c),
                                    key=f"unit_{h[:8]}",
                                    help="Função analisada pelo Módulo 1 e usada para a cobertura e a mutação.")
    calc = by_name[escolhida]

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
    return "(" + "; ".join(eg.fmt_s(a, pscales[i] if i < len(pscales) else 2) for i, a in enumerate(args)) + ")"


def tipo_icon(t):
    return ("🟢 " if t.startswith("Válida") else "🔴 ") + t


def cls_icon(c):
    return "🟢 " if c in ("Válida", "Ramo F") else "🔴 "


def eps_txt(e):
    return str(e).replace(".", ",")


def br_num(x, nd=2):
    return f"{x:,.{nd}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def esp_txt(v):
    return "—" if v is None else eg.fmt_s(v, rscale)


# ---------------------------------------------------------------------------
# Dados do Módulo 1 (usados em várias abas)
# ---------------------------------------------------------------------------
suite, resultados, cfg_calc, ei, rule, rules, pce_rows = None, None, None, None, None, None, None
escala, escalas, rscale, testavel, pscales = 2, {}, 2, False, []
orc_key = nz_key = ""
default_expr, orc_expr, orc_fn, orc_err = "", "", None, ""
if calc:
    tipo_k, prec, escala = eg.detect_type(calc, source)
    ei = eg.epsilon_info(prec, escala, tipo_k)
    rules = eg.derive_rules(calc, ei["epsilon"])
    rule = rules[0]
    pce_rows = eg.build_pce(calc, rules)
    cfg_calc = eg.build_cfg(calc, True)
    escalas, rscale = eg.func_scales(calc, escala), eg.result_scale(calc, escala)
    pscales = [escalas.get(p, escala) for p in calc.params]
    testavel = eg.is_testable(calc)
    orc_key, nz_key = f"orc_{h[:8]}_{calc.name}", f"nz_{h[:8]}_{calc.name}"
    default_expr = eg.default_oracle_expr(calc)
    orc_expr = st.session_state.get(orc_key, default_expr)
    if orc_expr.strip():
        try:
            orc_fn = eg.compile_oracle(orc_expr, calc.params, rscale, st.session_state.get(nz_key, True))
        except ValueError as ex:
            orc_err = str(ex)
    if testavel:
        suite = eg.build_suite(calc, rules, orc_fn)
        resultados = eg.run_suite(cfg_calc, suite, escala, escalas, rscale)

tabs = st.tabs([
    "Fonte",
    "Módulo 1: Caixa-preta",
    "Módulo 2: Caixa-branca",
    "Módulo 3: Fluxo de dados e mutação",
    "Módulo 4: Validação",
])

# ===========================================================================
# ABA 0 — Fonte
# ===========================================================================
with tabs[0]:
    st.subheader("Código-fonte analisado")
    st.caption(f"Arquivo: **{origem}** · o texto abaixo é editável — todas as abas analisam o que está na caixa. "
               "Experimente alterar o código (por exemplo, remover uma validação) e veja a análise reagir.")
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
        note("Nenhuma função com parâmetros encontrada para a análise de caixa-preta.", "warn")
    else:
        st.caption(f"Unidade sob teste: `{calc.name}({', '.join(calc.params)})`")
        sub = st.tabs(["Relatório (PCE & AVL)", "Gráfico de Fronteira",
                       "Execução com oráculo", "Parecer do Gemini"])

        # -- Relatório -------------------------------------------------------
        with sub[0]:
            st.markdown("#### Épsilon (ε) calculado a partir do tipo de dado")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Tipo", ei["label"])
            c2.metric("Épsilon ε", eps_txt(ei["epsilon"]))
            c3.metric("Fórmula", f"10^-{ei['scale']}")
            c4.metric("Máximo do tipo", br_num(ei["max"], 0 if ei["scale"] == 0 else 2))
            unid = "1 centavo" if ei["scale"] == 2 else "a menor unidade do tipo"
            note(
                f"<b>Por que ε = {eps_txt(ei['epsilon'])}?</b> O dado tem {ei['scale']} casa(s) decimal(is), então a menor "
                f"variação fisicamente representável é 10<sup>-{ei['scale']}</sup> = {eps_txt(ei['epsilon'])} ({unid}). "
                "Um passo menor seria arredondado para o mesmo valor e não criaria um ponto de teste distinto; "
                "um passo maior poderia saltar sobre o defeito de fronteira (operadores &lt; vs &lt;=).",
                "info",
            )
            st.markdown("**ε por parâmetro** (cada fronteira usa o ε do tipo da variável comparada)")
            st.dataframe(pd.DataFrame([{"Parâmetro": r["Parâmetro"], "Tipo": r["Tipo"],
                                        "Casas decimais": r["Casas decimais"], "ε": eps_txt(r["ε"])}
                                       for r in eg.param_eps_table(calc, escala)]), hide_index=True)
            if rule["kind"] == "padrao":
                note("<b>Possível defeito:</b> o código analisado não compara nenhum parâmetro com uma constante (por exemplo, "
                     "não valida valores negativos). A AVL abaixo usa a fronteira padrão em 0,00, que é a regra de negócio "
                     "esperada. A aba “Execução com oráculo” e a coluna “Obtido no código” do gráfico mostram o que o fonte, "
                     "sem ser alterado, realmente devolve nesses pontos.", "bad")
            if any(not eg.is_numeric_var(calc, p) for p in calc.params):
                note("Há parâmetros não numéricos (CHAR, DATE...). A PCE e a AVL abaixo cobrem as fronteiras numéricas; "
                     "os demais parâmetros precisam de classes definidas manualmente.", "warn")

            st.markdown("#### Particionamento em Classes de Equivalência (PCE)")
            df_pce = pd.DataFrame(pce_rows)
            df_pce["Tipo"] = df_pce["Tipo"].map(tipo_icon)
            st.dataframe(df_pce, hide_index=True)
            if any(r["Tipo"].startswith("Válida (tratada") for r in pce_rows):
                note("<b>Observação sobre NULL:</b> o código converte <code>NULL</code> em 0 antes de continuar. Esta ferramenta "
                     "segue o comportamento do código (nulo = válido). Se a especificação trata nulo como inválido, isso é "
                     "uma divergência a confirmar.", "warn")

            st.markdown("#### Análise do Valor Limite (AVL)")
            avl_rows = []
            for r in rules:
                cond = f"{' / '.join(r['vars']) or 'x'} {r['op']} {eg.fmt_s(r['c'], r['scale'])}"
                alvo = ", ".join(calc.params[i] for i in eg.rule_targets(calc, r))
                tipo_f = {"validacao": f"Validação (retorna {r['err_code']})", "decisao": "Decisão (ramos V/F)",
                          "padrao": "Padrão do laboratório"}[r["kind"]]
                lado_v, lado_i = (("ramo F", "ramo V") if r["kind"] == "decisao" else ("região válida", "região inválida"))
                just = {
                    "On": "Exatamente sobre a fronteira.",
                    "Off": f"Primeiro valor do outro lado da fronteira (passo de ε = {eps_txt(r['eps'])}).",
                    "Interior": f"Profundamente dentro da {lado_v}.",
                    "Exterior": f"Profundamente dentro da {lado_i}.",
                }
                for p in r["points"]:
                    avl_rows.append({"Entrada": alvo, "Ponto": p["ponto"], "Valor de teste": eg.fmt_s(p["valor"], r["scale"]),
                                     "Fronteira": cond, "Tipo de fronteira": tipo_f,
                                     "Classe": cls_icon(p["classe"]) + p["classe"],
                                     "Resultado esperado": p["esperado"], "Justificativa": just[p["ponto"]]})
            st.dataframe(pd.DataFrame(avl_rows), hide_index=True)

            if suite:
                st.markdown("#### Casos de teste derivados")
                df_ct = pd.DataFrame([{"ID": c["id"], "Técnica": c["tecnica"], "Descrição": c["descricao"],
                                       "Entrada": entrada_txt(c["args"]), "Resultado esperado": esp_txt(c["esperado"])}
                                      for c in suite])
                st.dataframe(df_ct, hide_index=True)
                st.download_button("⬇️ Baixar casos de teste (CSV)", df_csv(df_ct), "casos_de_teste.csv", "text/csv")
                if orc_fn:
                    st.caption("O resultado esperado vem de um **oráculo externo** (a regra de negócio que você definiu na aba "
                               "“Execução com oráculo”), nunca do próprio código-fonte.")
                else:
                    st.caption("Resultado esperado em branco: defina o **oráculo** (regra de negócio) na aba “Execução com oráculo”.")
            elif not testavel:
                note("Os casos de teste não foram gerados porque a unidade não é executável pelo interpretador interno "
                     "(usa SQL, CALL, texto ou outros comandos). A PCE e a AVL acima continuam valendo para elaborar os "
                     "casos manualmente.", "info")

        # -- Gráfico ---------------------------------------------------------
        with sub[1]:
            st.markdown("#### Pontos de fronteira (AVL)")
            rsel = rule
            if len(rules) > 1:
                opcoes = [f"{' / '.join(r['vars']) or 'x'} {r['op']} {eg.fmt_s(r['c'], r['scale'])}" for r in rules]
                rsel = rules[opcoes.index(st.selectbox("Fronteira", opcoes, key="avl_rule"))]
            pts = pd.DataFrame([{"Ponto": p["ponto"], "Valor": float(p["valor"]), "Classe": p["classe"],
                                 "Rótulo": f"{p['ponto']} ({eg.fmt_s(p['valor'], rsel['scale'])})", "Esperado": p["esperado"]}
                                for p in rsel["points"]])
            ordem = list(pts.sort_values("Valor")["Ponto"])
            base = alt.Chart(pts)
            linha = alt.Chart(pd.DataFrame({"x": [float(rsel["c"])]})).mark_rule(
                strokeDash=[6, 4], color="#8D8DA3", size=2).encode(x="x:Q")
            bolas = base.mark_circle(size=320).encode(
                x=alt.X("Valor:Q", title="Valor de entrada"),
                y=alt.Y("Ponto:N", sort=ordem, title=None),
                color=alt.Color("Classe:N", scale=alt.Scale(
                    domain=[c for c in ["Válida", "Ramo F", "Inválida", "Ramo V"] if c in set(pts["Classe"])],
                    range=[("#2FBF71" if c in ("Válida", "Ramo F") else "#FF5A7A")
                           for c in ["Válida", "Ramo F", "Inválida", "Ramo V"] if c in set(pts["Classe"])])),
                tooltip=["Ponto", "Valor", "Classe", "Esperado"])
            textos = base.mark_text(dy=-20, fontSize=12, color="#8D8DA3").encode(
                x="Valor:Q", y=alt.Y("Ponto:N", sort=ordem), text="Rótulo:N")
            st.altair_chart((linha + bolas + textos).properties(height=260, width="container")
                            .configure_view(stroke=None)
                            .configure_axis(gridColor="rgba(127,127,127,0.22)", domainColor="rgba(127,127,127,0.5)",
                                            tickColor="rgba(127,127,127,0.5)", labelFontSize=12))
            st.caption("Linha tracejada = fronteira. Verde = região válida (ou ramo F) · vermelho = região inválida (ou ramo V).")
            tab = pts[["Ponto", "Valor", "Classe", "Esperado"]].copy()
            if testavel and suite:
                alvo_i = eg.rule_targets(calc, rsel)[0]

                def obtido_no_ponto(v):
                    a = list(suite[0]["args"])
                    a[alvo_i] = D(str(v))
                    try:
                        return eg.fmt_s(eg.run_cfg(cfg_calc, a, escala, scales=escalas)["result"], rscale)
                    except Exception:                     # noqa: BLE001
                        return "erro"

                tab[f"Obtido no código ({calc.params[alvo_i]})"] = [obtido_no_ponto(v) for v in pts["Valor"]]
            tab["Valor"] = tab["Valor"].map(lambda v: eg.fmt_s(D(str(v)), rsel["scale"]))
            st.dataframe(tab, hide_index=True)

        # -- Execução --------------------------------------------------------
        with sub[2]:
            st.markdown("#### Oráculo: resultado esperado (regra de negócio)")
            a = calc.params
            exemplo = f"-1 if {a[0]} < 0 else {a[0]}" + (f" * {a[1]}" if len(a) > 1 else "")
            st.caption("O oráculo é a regra da **especificação**, nunca o código-fonte. Escreva-a como uma expressão "
                       f"(sintaxe Python). Variáveis: `{', '.join(a)}` (ou `p1`…`p{len(a)}`). "
                       "Operadores: `+ - * / %`, comparações, `and/or/not`, `A if condição else B`, `abs/min/max`.")
            st.text_area("Expressão do oráculo", value=default_expr, key=orc_key, height=90,
                         placeholder=f"Exemplo: {exemplo}", label_visibility="collapsed")
            st.checkbox("Tratar NULL como 0 no oráculo (como o código faz)", value=True, key=nz_key)
            if orc_err:
                note(f"Oráculo inválido: {orc_err}", "bad")
            elif not orc_fn:
                note("Nenhum oráculo definido: os casos aparecem com o resultado <b>obtido</b>, mas sem aprovado/reprovado. "
                     "Escreva a regra de negócio acima para validar o código.", "info")

            if not resultados:
                note("A unidade não é executável pelo interpretador interno (usa SQL, CALL, texto ou outros comandos).", "warn")
            else:
                n_ok = sum(r["ok"] is True for r in resultados)
                n_bad = sum(r["ok"] is False for r in resultados)
                n_na = sum(r["ok"] is None for r in resultados)
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Casos executados", len(resultados))
                c2.metric("Passaram ✅", n_ok)
                c3.metric("Falharam ❌", n_bad)
                c4.metric("Sem oráculo", n_na)
                if orc_fn and n_bad == 0:
                    note("Todos os casos de teste passaram: o código respeita o oráculo.")
                elif orc_fn:
                    falhas = [r for r in resultados if r["ok"] is False]
                    so_neg = all(any(isinstance(x, D) and x < 0 for x in r["args"]) for r in falhas)
                    extra = (" Todas as falhas envolvem valores negativos: o código não os rejeita como a regra esperada "
                             "exige (veja a coluna “Obtido”)." if so_neg else "")
                    note("Há falhas — os casos que não passam revelam onde o código diverge da regra de negócio "
                         "(ex.: uma validação ausente)." + extra, "bad")
                df_ex = pd.DataFrame([{
                    "ID": r["id"], "Técnica": r["tecnica"], "Entrada": entrada_txt(r["args"]),
                    "Esperado (oráculo)": esp_txt(r["esperado"]),
                    "Obtido": eg.fmt_s(r["obtido"], rscale) if not r["erro"] else r["erro"],
                    "Resultado": {True: "✅ passou", False: "❌ falhou", None: "— sem oráculo"}[r["ok"]],
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

                linhas_as = ["from decimal import Decimal as D", "", "# oráculo = regra de negócio externa, não o código-fonte"]
                for c in suite:
                    if c["esperado"] is None:
                        continue
                    args = ", ".join("None" if x is None else f"D('{x}')" for x in c["args"])
                    linhas_as.append(f"assert {calc.name}({args}) == D('{c['esperado']}'), \"{c['id']}: {c['descricao']}\"")
                if len(linhas_as) > 3:
                    st.markdown("**Oráculos de asserção:** a suíte como código executável")
                    st.code("\n".join(linhas_as), language="python")

        # -- IA --------------------------------------------------------------
        with sub[3]:
            ctx = (f"Épsilon calculado: {ei['epsilon']} ({ei['label']}).\n"
                   f"Fronteiras encontradas no código: {[(r['op'], str(r['c']), r['vars']) for r in rules]} "
                   f"(derivadas do código: {rule['from_code']}).\n"
                   "PCE:\n" + pd.DataFrame(pce_rows).to_csv(index=False))
            if orc_fn:
                ctx += f"\nOráculo definido pelo testador: {orc_expr}\n"
            if resultados:
                ctx += "\nResultado da execução da suíte:\n" + "\n".join(
                    f"{r['id']} {entrada_txt(r['args'])} esperado={esp_txt(r['esperado'])} obtido={eg.fmt(r['obtido'])} ok={r['ok']}"
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
             "(GOTO, EXIT/CONTINUE...).", "warn")
    fluxo = eg.unsupported_flow(fsel)
    if fluxo:
        note("<b>Atenção:</b> o fonte usa " + ", ".join(f"<code>{x}</code>" for x in fluxo) + ", que esta ferramenta não "
             "modela no GFC. O V(G) calculado pode estar subestimado: confira o grafo manualmente.", "warn")

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
# ABA 3 — Módulo 3: Fluxo de dados e mutação (duas sub-abas)
# ===========================================================================
with tabs[3]:
    sub3 = st.tabs(["Fluxo de dados (pares DU)", "Teste de mutação"])

with sub3[0]:
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
# Módulo 3 (continuação): Teste de mutação
# ===========================================================================
@st.cache_data(show_spinner="Gerando e executando mutantes...")
def mutacao_cached(fonte: str, fname: str, ids: tuple):
    fs = {f.name: f for f in eg.split_functions(fonte)}
    f = fs[fname]
    kd, pr, sc = eg.detect_type(f, fonte)
    e = eg.epsilon_info(pr, sc, kd)
    su = [c for c in eg.build_suite(f, eg.derive_rules(f, e["epsilon"])) if c["id"] in ids]
    return eg.run_mutation(f, su, sc)


with sub3[1]:
    st.subheader("Módulo 3: Teste de mutação: quão boa é a sua suíte de testes?")
    st.caption("Injetamos defeitos propositais (mutantes) e verificamos se os testes “matam” cada um.")
    if not (calc and suite):
        note("A mutação requer uma unidade executável pelo interpretador interno: parâmetros numéricos e comandos LET/RETURN/IF/laços (sem SQL, CALL ou texto).", "warn")
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

# ===========================================================================
# ABA 4 — Módulo 4: Validação
# ===========================================================================
OK_, WARN_, BAD_, NA_ = "✅ Ok", "⚠️ Atenção", "❌ Falha", "➖ Não avaliado"

with tabs[4]:
    st.subheader("Módulo 4: Validação dos resultados")
    st.caption("Prova de que o que foi pedido foi testado (e o que foi testado foi pedido), mais um painel técnico "
               "com as verificações dos módulos 1 a 3.")
    if not calc:
        note("Nenhuma função com parâmetros encontrada: não há unidade para validar.", "warn")
    else:
        base_k = f"{h[:8]}_{calc.name}"
        ver_k, sug_k = f"rtm_ver_{base_k}", f"rtm_sug_{base_k}"
        ver = st.session_state.get(ver_k, 0)
        rtm = None
        sub_v = st.tabs(["Matriz de rastreabilidade (RTM)", "Painel de validação técnica"])
        with sub_v[0]:
            FLUXOS_COL = ("Caminho feliz", "Fluxo alternativo", "Fluxo de exceção")

            def _s(x):
                return "" if x is None or (isinstance(x, float) and x != x) else str(x).strip()


            st.markdown("#### 1. Requisitos: o que foi pedido")
            st.caption("Liste os requisitos do cenário com IDs como REQ01, REQ02… Para o CAD0001 há uma sugestão a partir do manual; "
                       "ajuste conforme a especificação. Em outros programas, cadastre os seus.")
            req_default = [{"ID": i, "Requisito": t} for i, t in eg.default_requirements(calc)] or [{"ID": "", "Requisito": ""}]
            req_ed = st.data_editor(pd.DataFrame(req_default), num_rows="dynamic", hide_index=True, key=f"rtm_req_{base_k}",
                                    column_config={"ID": st.column_config.TextColumn("ID", width="small"),
                                                   "Requisito": st.column_config.TextColumn("Requisito", width="large")})
            reqs_in = [{"id": _s(r.get("ID")), "texto": _s(r.get("Requisito"))} for r in req_ed.to_dict("records") if _s(r.get("ID"))]

            st.markdown("#### 2. Casos de teste e rastreio: o que foi testado")
            sug = st.session_state.get(sug_k)
            cts_in = []
            if suite:
                st.caption("Os casos abaixo vêm da suíte caixa-preta (PCE + AVL) e já foram executados. Preencha a coluna "
                           "**Requisitos** com os IDs que cada caso valida (ex.: `REQ01, REQ03`).")
                if reqs_in and st.button("Sugerir rastreio com Gemini", key=f"btn_rtm_{base_k}"):
                    if not api_key.strip():
                        st.warning("Informe a Gemini API Key (Secrets ou barra lateral).")
                    else:
                        txt_ia = None
                        with st.spinner(f"Consultando {modelo}..."):
                            try:
                                lista_cts = "\n".join(f"{c['id']} [{eg.classify_flow(calc, rules, c)}]: {c['descricao']}; entrada {entrada_txt(c['args'])}"
                                                      for c in suite)
                                lista_reqs = "\n".join(f"{r['id']}: {r['texto']}" for r in reqs_in)
                                cliente = genai.Client(api_key=api_key)
                                txt_ia = cliente.models.generate_content(model=modelo, contents=(
                                    "Você é um analista de testes. Relacione cada caso de teste aos requisitos que ele ajuda a validar.\n\n"
                                    f"Requisitos:\n{lista_reqs}\n\nCasos de teste:\n{lista_cts}\n\n"
                                    'Responda SOMENTE com um JSON no formato {"CT01": ["REQ01"], "CT02": ["REQ02", "REQ03"]}, '
                                    "usando apenas os IDs listados. Omita casos que não se relacionem a nenhum requisito.")).text
                            except Exception as ex:  # noqa: BLE001
                                st.error(f"Erro ao chamar a Gemini API ({modelo}): {ex}")
                        if txt_ia is not None:
                            mapa = eg.parse_trace_json(txt_ia, [r["id"] for r in reqs_in], [c["id"] for c in suite])
                            if mapa:
                                st.session_state[sug_k] = mapa
                                st.session_state[ver_k] = ver + 1
                                st.rerun()
                            else:
                                st.warning("A IA não devolveu um rastreio utilizável; mantive o atual.")
                if sug is not None:
                    note("Rastreio sugerido pela IA: revise cada linha antes de usar. A IA não substitui o seu critério.", "info")
                linhas = []
                for c in suite:
                    fl = eg.classify_flow(calc, rules, c)
                    refs = ", ".join(sug.get(c["id"], [])) if sug is not None else eg.default_trace(calc, c, fl)
                    linhas.append({"ID": c["id"], "Fluxo": fl, "Descrição": c["descricao"], "Requisitos": refs})
                tr_ed = st.data_editor(pd.DataFrame(linhas), hide_index=True, disabled=["ID", "Fluxo", "Descrição"],
                                       key=f"rtm_tr_{base_k}_{ver}")
                res_map = {r["id"]: {True: "Passou", False: "Falhou", None: "Sem oráculo"}[r["ok"]] for r in (resultados or [])}
                for r in tr_ed.to_dict("records"):
                    cts_in.append({"id": r["ID"], "tipo": r["Fluxo"], "descricao": r["Descrição"], "reqs": _s(r.get("Requisitos")),
                                   "resultado": res_map.get(r["ID"], "Não executado")})
            else:
                note("A unidade não gera casos executáveis (usa SQL, CALL, texto...). Cadastre os casos de teste manualmente abaixo.", "info")

            st.markdown("#### 3. Casos de teste manuais (opcional)")
            st.caption("Para requisitos que o app não executa (tela, e-mail, banco de dados...). Informe o fluxo, os requisitos e o resultado.")
            man_ed = st.data_editor(
                pd.DataFrame({"ID": pd.Series(dtype="str"), "Fluxo": pd.Series(dtype="str"), "Descrição": pd.Series(dtype="str"),
                              "Requisitos": pd.Series(dtype="str"), "Resultado": pd.Series(dtype="str")}),
                num_rows="dynamic", hide_index=True, key=f"rtm_man_{base_k}",
                column_config={"Fluxo": st.column_config.SelectboxColumn("Fluxo", options=list(eg.FLUXOS)),
                               "Resultado": st.column_config.SelectboxColumn("Resultado", options=["Passou", "Falhou", "Não executado"])})
            for r in man_ed.to_dict("records"):
                if _s(r.get("ID")):
                    cts_in.append({"id": _s(r.get("ID")), "tipo": _s(r.get("Fluxo")), "descricao": _s(r.get("Descrição")),
                                   "reqs": _s(r.get("Requisitos")), "resultado": _s(r.get("Resultado")) or "Não executado"})

            rtm = eg.build_rtm(reqs_in, cts_in)
            st.markdown("#### 4. Matriz de Rastreabilidade de Requisitos (RTM)")
            if not rtm["req_ids"]:
                note("Cadastre ao menos um requisito (passo 1) para montar a matriz.", "info")
            else:
                fwd, bwd = rtm["fwd"], rtm["bwd"]
                n_val = sum(r["situacao"] == "Validado" for r in rtm["req_rows"])
                k = st.columns(5)
                k[0].metric("Requisitos", len(rtm["req_ids"]))
                k[1].metric("Casos de teste", len(rtm["ct_ids"]))
                k[2].metric("Requisitos cobertos", f"{fwd[0]}/{fwd[1]}", f"{fwd[0] / fwd[1] * 100:.0f}%" if fwd[1] else None)
                k[3].metric("Requisitos validados", f"{n_val}/{fwd[1]}", f"{n_val / fwd[1] * 100:.0f}%" if fwd[1] else None)
                k[4].metric("CTs rastreados", f"{bwd[0]}/{bwd[1]}", f"{bwd[0] / bwd[1] * 100:.0f}%" if bwd[1] else None)

                sem = [r["id"] for r in rtm["req_rows"] if not r["n_cts"]]
                if sem:
                    note("<b>Tudo o que foi pedido foi coberto? Não.</b> Requisitos sem nenhum caso de teste: " + ", ".join(sem) + ".", "bad")
                else:
                    note("<b>Tudo o que foi pedido foi coberto? Sim.</b> Todo requisito tem ao menos um caso de teste.")
                if rtm["orphans"] or rtm["unknown"]:
                    partes = []
                    if rtm["orphans"]:
                        partes.append("casos sem requisito: " + ", ".join(rtm["orphans"]))
                    if rtm["unknown"]:
                        partes.append("referências a requisitos inexistentes: " + "; ".join(f"{a} → {', '.join(b)}" for a, b in rtm["unknown"].items()))
                    note("<b>Tudo o que foi testado foi pedido? Não.</b> " + "; ".join(partes) + ".", "warn")
                else:
                    note("<b>Tudo o que foi testado foi pedido? Sim.</b> Todo caso de teste está ligado a um requisito existente.")
                if rtm["dup_reqs"] or rtm["dup_cts"]:
                    note("IDs repetidos foram ignorados: " + ", ".join(rtm["dup_reqs"] + rtm["dup_cts"]) + ".", "warn")

                icones = {"Validado": "✅ Validado", "Coberto, com falha": "❌ Coberto, com falha",
                          "Coberto, sem resultado": "⚠️ Coberto, sem resultado", "Sem cobertura": "🔴 Sem cobertura"}
                df_req = pd.DataFrame([{"Requisito": r["id"], "Descrição": r["texto"], "Nº de CTs": r["n_cts"],
                                        "Situação": icones[r["situacao"]],
                                        FLUXOS_COL[0]: "✔" if r["feliz"] else "—", FLUXOS_COL[1]: "✔" if r["alternativo"] else "—",
                                        FLUXOS_COL[2]: "✔" if r["excecao"] else "—"}
                                       for r in rtm["req_rows"]])
                st.dataframe(df_req, hide_index=True)
                st.markdown("**Matriz** (linhas = requisitos, colunas = casos de teste; ● = o caso valida o requisito)")
                df_m = pd.DataFrame({ct: ["●" if rtm["matrix"][rid][ct] else "" for rid in rtm["req_ids"]] for ct in rtm["ct_ids"]},
                                    index=rtm["req_ids"])
                st.dataframe(df_m)
                df_m_csv = df_m.copy()
                df_m_csv.insert(0, "Requisito", df_m_csv.index)
                st.download_button("⬇️ Baixar a matriz (CSV)", df_csv(df_m_csv), "matriz_rastreabilidade.csv", "text/csv")
        with sub_v[1]:
            # ---- dados reaproveitados dos módulos anteriores -----------------------
            mc_v = eg.mccabe(cfg_calc)
            fluxo_v = eg.unsupported_flow(calc)
            pares_v = eg.du_pairs(cfg_calc)
            info_v = eg.defuse_info(cfg_calc)
            cob_nos = cob_arestas = cob_du = None
            if resultados:
                cn_v = {n for r in resultados for n in r["trace"]}
                ce_v = {e for r in resultados for e in r["edges"]}
                cob_nos = (len(cn_v), len(cfg_calc.nodes))
                cob_arestas = (len(ce_v), len(cfg_calc.edges))
                trs_v = [r["trace"] for r in resultados]
                cob_du = (sum(any(eg.pair_covered(t, p, info_v) for t in trs_v) for p in pares_v), len(pares_v))
            ms_v = None
            if suite:
                try:
                    ms_v = eg.mutation_score(mutacao_cached(source, calc.name, tuple(c["id"] for c in suite)))
                except Exception:                                           # noqa: BLE001
                    ms_v = None
            n_ok_v = sum(r["ok"] is True for r in resultados) if resultados else 0
            n_bad_v = sum(r["ok"] is False for r in resultados) if resultados else 0

            def pct(a, b):
                return f"{a}/{b} ({a / b * 100:.0f}%)" if b else "0/0"

            # ---- A. validação da análise ---------------------------------------------
            A = []
            A.append(("Fonte", "Fonte analisado",
                      WARN_ if source != original else OK_,
                      ("Código editado na tela: difere do arquivo (o arquivo em si não é alterado)."
                       if source != original else
                       f"Idêntico ao arquivo {origem} (SHA-256 {hashlib.sha256(source.encode('utf-8')).hexdigest()[:10]}).")))
            A.append(("Módulo 1", "Épsilon coerente com o tipo",
                      OK_ if ei["epsilon"] == D(1).scaleb(-ei["scale"]) else BAD_,
                      f"ε = {eps_txt(ei['epsilon'])} para {ei['label']}"))
            linhas_por_param = [sum(r["Entrada"] == p for r in pce_rows) for p in calc.params]
            A.append(("Módulo 1", "PCE cobre todos os parâmetros",
                      OK_ if all(n >= 3 for n in linhas_por_param) else WARN_,
                      f"{len(calc.params)} parâmetro(s), {len(pce_rows)} classes de equivalência"))
            quatro = all({p["ponto"] for p in r["points"]} == {"On", "Off", "Interior", "Exterior"} for r in rules)
            padrao_v = any(r["kind"] == "padrao" for r in rules)
            A.append(("Módulo 1", "AVL com On, Off, Interior e Exterior",
                      (WARN_ if padrao_v else OK_) if quatro else BAD_,
                      (f"{len(rules)} fronteira(s), {4 * len(rules)} pontos"
                       + ("; fronteira padrão em 0,00 (o código não compara com constante)." if padrao_v else "."))))
            A.append(("Módulo 1", "Suíte de casos de teste gerada",
                      OK_ if suite else WARN_,
                      (f"{len(suite)} casos ({sum(c['tecnica'] == 'PCE' for c in suite)} PCE, "
                       f"{sum(c['tecnica'] == 'AVL' for c in suite)} AVL)") if suite
                      else "Unidade não executável pelo interpretador interno (SQL, CALL, texto...)."))
            A.append(("Módulo 2", "V(G): as três fórmulas concordam",
                      OK_ if mc_v["consistente"] else BAD_,
                      f"N={mc_v['N']}, E={mc_v['E']}, P={mc_v['P']}, R={mc_v['R']}, V(G)={mc_v['V_EN']}"))
            A.append(("Módulo 2", "Fluxo de controle totalmente modelado",
                      WARN_ if fluxo_v else OK_,
                      ("Usa " + ", ".join(fluxo_v) + ": V(G) pode estar subestimado.") if fluxo_v else "Sem EXIT/CONTINUE/GOTO."))
            A.append(("Módulo 2", "Casos de teste ≥ V(G)",
                      (OK_ if len(suite) >= mc_v["V_EN"] else WARN_) if suite else NA_,
                      (f"{len(suite)} casos para V(G) = {mc_v['V_EN']}" if suite else "Sem suíte executável.")))

            # ---- B. validação do código sob teste -----------------------------------
            B = []
            B.append(("Módulo 1", "Oráculo (regra de negócio) definido",
                      BAD_ if orc_err else (OK_ if orc_fn else WARN_),
                      f"Inválido: {orc_err}" if orc_err else ("Definido na aba Execução com oráculo." if orc_fn
                                                             else "Sem oráculo: os casos não têm aprovado/reprovado.")))
            B.append(("Módulo 1", "Código respeita o oráculo",
                      (OK_ if n_bad_v == 0 else BAD_) if (resultados and orc_fn) else NA_,
                      (f"{n_ok_v} de {len(resultados)} casos passam; {n_bad_v} falham." if (resultados and orc_fn)
                       else "Defina o oráculo para avaliar.")))
            B.append(("Módulo 2", "Cobertura de arestas pela suíte",
                      (OK_ if cob_arestas[0] == cob_arestas[1] else WARN_) if cob_arestas else NA_,
                      pct(*cob_arestas) if cob_arestas else "Sem suíte executável."))
            B.append(("Módulo 2", "Cobertura de nós pela suíte",
                      (OK_ if cob_nos[0] == cob_nos[1] else WARN_) if cob_nos else NA_,
                      pct(*cob_nos) if cob_nos else "Sem suíte executável."))
            B.append(("Módulo 3", "Todos-usos (pares definição-uso)",
                      (OK_ if cob_du[0] == cob_du[1] else WARN_) if cob_du else NA_,
                      (pct(*cob_du) + ("; pares restantes podem ser infactíveis." if cob_du[0] != cob_du[1] else ""))
                      if cob_du else "Sem suíte executável."))
            B.append(("Módulo 3", "Escore de mutação (MS)",
                      (OK_ if ms_v["MS"] >= 90 else (WARN_ if ms_v["MS"] >= 70 else BAD_)) if ms_v else NA_,
                      (f"MS = {ms_v['MS']:.1f}% ({ms_v['Md']} mortos de {ms_v['Mt'] - ms_v['Me']} não equivalentes)"
                       if ms_v else "Sem suíte executável.")))
            B.append(("Módulo 3", "Mutantes vivos",
                      (OK_ if (ms_v["Mt"] - ms_v["Me"] - ms_v["Md"]) == 0 else WARN_) if ms_v else NA_,
                      (f"{ms_v['Mt'] - ms_v['Me'] - ms_v['Md']} sobreviveram" if ms_v else "Sem suíte executável.")))

            todas = A + B
            cont = {s: sum(x[2] == s for x in todas) for s in (OK_, WARN_, BAD_, NA_)}
            k = st.columns(4)
            k[0].metric("Verificações", len(todas))
            k[1].metric("Ok ✅", cont[OK_])
            k[2].metric("Atenção ⚠️", cont[WARN_])
            k[3].metric("Falhas ❌", cont[BAD_])

            falhas_v = [x[1] for x in todas if x[2] == BAD_]
            avisos_v = [x[1] for x in todas if x[2] == WARN_]
            if falhas_v:
                note("<b>Há falhas a tratar:</b> " + "; ".join(falhas_v) + ". Se forem falhas do código sob teste "
                     "(oráculo, mutação), elas indicam defeitos encontrados; se forem da análise, revise o fonte.", "bad")
            elif avisos_v:
                note("<b>Análise válida com ressalvas:</b> " + "; ".join(avisos_v) + ".", "warn")
            else:
                note("<b>Tudo validado:</b> a análise é consistente e o código passa em todas as verificações.")

            df_cols = ["Módulo", "Verificação", "Status", "Detalhe"]
            st.markdown("#### Validação da análise (a ferramenta é consistente?)")
            st.dataframe(pd.DataFrame(A, columns=df_cols), hide_index=True)
            st.markdown("#### Validação do código sob teste (o código está bem testado e correto?)")
            st.dataframe(pd.DataFrame(B, columns=df_cols), hide_index=True)

            md = [f"# Relatório de validação: {origem}", "",
                  f"Unidade sob teste: `{calc.name}({', '.join(calc.params)})`", "",
                  "## Validação da análise", "", "| Módulo | Verificação | Status | Detalhe |", "|---|---|---|---|"]
            md += [f"| {m} | {v} | {s} | {d} |" for m, v, s, d in A]
            md += ["", "## Validação do código sob teste", "", "| Módulo | Verificação | Status | Detalhe |", "|---|---|---|---|"]
            md += [f"| {m} | {v} | {s} | {d} |" for m, v, s, d in B]
            md += [""]
            relatorio_md = "\n".join(md) + "\n" + eg.rtm_markdown(rtm)
            st.download_button("⬇️ Baixar relatório de validação (.md)", relatorio_md.encode("utf-8"),
                               "relatorio_validacao.md", "text/markdown")

            parecer_ia("m4", f"""Você é um especialista em teste de software. Com base no relatório de validação abaixo,
    calculado por uma ferramenta determinística, escreva em português: (1) as principais limitações e riscos da
    análise; (2) lacunas na rastreabilidade entre requisitos e casos de teste; (3) o que você validaria a mais antes de
    confiar no resultado. Não invente números que não estejam no relatório.

    {relatorio_md}""")

st.divider()
st.caption("TestingStudio Web")
