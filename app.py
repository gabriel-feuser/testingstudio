import os
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai

st.set_page_config(
    page_title="TestingStudio Web",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 TestingStudio Web")
st.caption("Análise de Testes de Software — PCE + AVL | CAD0001")

# ---------------------------------------------------------------------------
# Sidebar: autenticação e modelo
# ---------------------------------------------------------------------------
st.sidebar.header("Configuração")

# A chave NÃO fica no código: vem dos Secrets do Streamlit.
NOMES_ACEITOS = {"gemini_api_key", "google_api_key", "gemini_key", "api_key"}


def _limpar(valor):
    return str(valor).strip().strip("\"'").strip()


def obter_chave_dos_secrets():
    """Procura a chave nos Secrets (nível raiz ou dentro de seções) e nas
    variáveis de ambiente. Retorna (chave, nomes_encontrados)."""
    nomes_encontrados = []

    try:
        for nome in st.secrets:
            valor = st.secrets[nome]
            nomes_encontrados.append(str(nome))

            if hasattr(valor, "items"):  # seção [alguma_secao]
                for nome2, valor2 in valor.items():
                    nomes_encontrados.append(f"{nome}.{nome2}")
                    if str(nome2).lower() in NOMES_ACEITOS and _limpar(valor2):
                        return _limpar(valor2), nomes_encontrados
            elif str(nome).lower() in NOMES_ACEITOS and _limpar(valor):
                return _limpar(valor), nomes_encontrados
    except Exception:
        pass

    for nome_env in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if _limpar(os.environ.get(nome_env, "")):
            return _limpar(os.environ[nome_env]), nomes_encontrados

    return "", nomes_encontrados


api_key, nomes_secrets = obter_chave_dos_secrets()

if api_key:
    st.sidebar.success("Chave carregada dos Secrets.")
else:
    st.sidebar.error(
        "Nenhuma chave encontrada nos Secrets. Configure "
        "GEMINI_API_KEY em Settings → Secrets, ou digite abaixo."
    )
    st.sidebar.caption(
        "Secrets detectados (só os nomes): "
        + (", ".join(nomes_secrets) if nomes_secrets else "nenhum")
    )
    api_key = st.sidebar.text_input(
        "Gemini API Key (alternativa):",
        type="password",
        help="Só é necessário se os Secrets não estiverem configurados."
    )

fallback_models = [
    "gemini-3.8-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3-flash",
    "gemini-2.5-flash",
]


@st.cache_data(show_spinner=False, ttl=3600)
def listar_modelos(chave: str):
    """Consulta a Gemini API e devolve os modelos que suportam generateContent."""
    modelos = []
    try:
        client = genai.Client(api_key=chave)
        for model_info in client.models.list():
            name = getattr(model_info, "name", "")
            actions = getattr(model_info, "supported_actions", []) or []
            if "generateContent" in actions and name.startswith("models/gemini-"):
                modelos.append(name.replace("models/", ""))
    except Exception:
        pass
    return modelos


available_models = listar_modelos(api_key) if api_key.strip() else []
if not available_models:
    available_models = fallback_models
available_models = list(dict.fromkeys(available_models))

default_model = (
    "gemini-3.6-flash"
    if "gemini-3.6-flash" in available_models
    else available_models[0]
)

selected_model = st.sidebar.selectbox(
    "Modelo Gemini:",
    available_models,
    index=available_models.index(default_model),
    help="Escolha qual modelo será usado na análise PCE + AVL."
)
st.sidebar.caption(f"Modelo selecionado: `{selected_model}`")

# ---------------------------------------------------------------------------
# Leitura do código-fonte (caminho relativo ao app.py, funciona no deploy)
# ---------------------------------------------------------------------------
source_file = Path(__file__).parent / "cad0001_item_calculo.txt"

try:
    source_code = source_file.read_text(encoding="utf-8")
except FileNotFoundError:
    st.error(
        f"Não encontrei o arquivo '{source_file.name}'. "
        "Coloque o .txt na mesma pasta do app.py."
    )
    st.stop()

st.subheader("Código-fonte analisado")
st.text_area(
    "cad0001_item_calculo.txt",
    source_code,
    height=420
)


# ---------------------------------------------------------------------------
# Análise com Gemini
# ---------------------------------------------------------------------------
def analisar_com_gemini(api_key, source_code, model):
    client = genai.Client(api_key=api_key)

    prompt = f"""
Você é um analista de testes de software.

Analise SOMENTE o código-fonte fornecido abaixo. Não invente regras de negócio
que não estejam presentes no código.

Objetivo: realizar uma análise funcional de caixa-preta usando:
1. Particionamento em Classes de Equivalência (PCE)
2. Análise de Valor Limite (AVL)

Considere epsilon = 0,01 para valores decimais/monetários. Justifique essa
escolha: os parâmetros são DECIMAL(12,2), ou seja, a menor variação possível
é 1 centavo (0,01).

Importante:
- Identifique as regras de negócio realmente presentes no código
  (tratamento de nulos, validação de negativos com RETURN -1, fórmula).
- Valores nulos são tratados como 0 antes da validação.
- Não altere nem invente a fórmula existente.
- Diferencie comportamento observado no código de uma hipótese de teste.
- Para AVL, apresente On, Off, Interior e Exterior (fronteira em 0,00):
  On = 0,00 | Off = -0,01 | Interior = 100,00 | Exterior = -100,00.
- Mostre valores concretos de teste e o resultado esperado
  (cálculo normal ou retorno -1).
- Explique brevemente o motivo de cada classe e cada valor-limite.

Organize a resposta nestas seções:

## 1. Regras identificadas no código

## 2. PCE
Crie uma tabela com:
- Entrada/Condição
- Classe
- Tipo (Válida/Inválida)
- Justificativa

## 3. AVL (com justificativa do épsilon)
Crie uma tabela com:
- Entrada
- Ponto
- Valor de teste
- Resultado esperado
- Justificativa

## 4. Casos de teste
Crie uma tabela com:
- ID
- Entrada
- Resultado esperado
- Técnica (PCE/AVL)

## 5. Observação sobre limitações
Explique qualquer regra que o código não implemente, mas que seria relevante
para os testes (por exemplo: o que as rotinas de inclusão e alteração fazem
com o retorno -1).

Código-fonte:
----------------
{source_code}
----------------
"""

    response = client.models.generate_content(model=model, contents=prompt)
    return response.text


# ---------------------------------------------------------------------------
# Dados da AVL (conforme o manual da Sprint 1)
# ---------------------------------------------------------------------------
avl_data = pd.DataFrame([
    {"Ponto": "On",       "Valor": 0.00,    "Interpretação": "Exatamente na fronteira válida",
     "Resultado esperado": "Sucesso (cálculo OK)"},
    {"Ponto": "Off",      "Valor": -0.01,   "Interpretação": "Primeiro ponto fora (0,00 − ε)",
     "Resultado esperado": "Erro (-1)"},
    {"Ponto": "Interior", "Valor": 100.00,  "Interpretação": "Profundamente na região válida",
     "Resultado esperado": "Sucesso (cálculo OK)"},
    {"Ponto": "Exterior", "Valor": -100.00, "Interpretação": "Profundamente na região inválida",
     "Resultado esperado": "Erro (-1)"},
])
avl_data["Rótulo"] = avl_data.apply(
    lambda r: f"{r['Ponto']} ({r['Valor']:.2f})", axis=1
)

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
if st.button("Executar análise PCE + AVL", type="primary"):
    if not api_key.strip():
        st.warning("Informe sua Gemini API Key na barra lateral.")
    else:
        with st.spinner(f"Analisando o código com {selected_model}..."):
            try:
                st.session_state["resultado"] = analisar_com_gemini(
                    api_key, source_code, selected_model
                )
            except Exception as e:
                st.session_state.pop("resultado", None)
                st.error(
                    f"Erro ao chamar a Gemini API usando o modelo "
                    f"{selected_model}: {e}"
                )
                st.info(
                    "Tente selecionar outro modelo na barra lateral. "
                    "Se o erro continuar, verifique a disponibilidade "
                    "do modelo para sua chave."
                )

tab1, tab2 = st.tabs(["📋 Relatório (PCE & AVL)", "📊 Gráfico de Fronteira"])

with tab1:
    if "resultado" in st.session_state:
        st.markdown(st.session_state["resultado"])
    else:
        st.caption("Clique em “Executar análise PCE + AVL” para gerar o relatório.")

with tab2:
    st.subheader("Pontos Limites (AVL) — ε = 0,01")
    st.bar_chart(avl_data, x="Rótulo", y="Valor")
    st.dataframe(
        avl_data[["Ponto", "Valor", "Interpretação", "Resultado esperado"]],
        hide_index=True
    )
    st.info(
        "O código analisado valida os parâmetros: se qualquer um for "
        "negativo (< 0,00), a função retorna -1. Nulos são tratados como 0."
    )

st.divider()
st.caption("Projeto acadêmico — TestingStudio Web")
