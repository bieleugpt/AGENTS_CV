


#AXA_IA/__axa/agent_cv/app/ui.py

import sys
import os


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

import importlib

import streamlit as st

import config.settings as settings
importlib.reload(settings)

from agent.orchestrator import run_agent
from config.settings import AVAILABLE_SITES

print("ROOT_DIR =", ROOT_DIR)
print("settings file =", settings.__file__)
print("AVAILABLE_SITES =", settings.AVAILABLE_SITES)
print("sys.path[0:5] =", sys.path[:5])


# =========================================================
# CONFIG PAGE
# =========================================================
st.set_page_config(
    page_title="AXA IA - Search Agent",
    layout="wide"
)

# =========================================================
# HEADER
# =========================================================
st.title("🔍 AXA IA - Intelligent Search Agent")

# =========================================================
# SIDEBAR (CONFIG UTILISATEUR)
# =========================================================
st.sidebar.header("⚙️ Configuration")

mode = st.sidebar.selectbox(
    "Mode",
    ["Recherche", "Analyse incident"]
)

selected_sites = st.sidebar.multiselect(
    "Sources",
    settings.AVAILABLE_SITES,
    default=settings.AVAILABLE_SITES[:1]
)

# =========================================================
# MAIN INPUT
# =========================================================
st.subheader("🔎 Recherche")

query = st.text_area(
    "Votre demande",
    placeholder="Ex: Trouve les incidents critiques sur le site X..."
)

launch = st.button("🚀 Lancer la recherche")

# =========================================================
# EXECUTION
# =========================================================
if launch and query:

    with st.spinner("Analyse en cours..."):

        '''
        result = run_agent(
            query=query,
            mode=mode,
            sources=selected_sites
        )
        '''
        
        try:
            result = run_agent(
                query=query,
                mode=mode,
                sources=selected_sites
            )
        except Exception as e:
            st.error(f"Erreur système: {str(e)}")
            st.stop()

    

    # =====================================================
    # RESULT DISPLAY
    # =====================================================
    st.success("Résultat")

    st.markdown("### 📌 Résumé")
    st.write(result.get("summary", "N/A"))

    st.markdown("### 📊 Données clés")
    st.write(result.get("data", "N/A"))

    st.markdown("### ⚠️ Problèmes détectés")
    st.write(result.get("issues", "N/A"))

    st.markdown("### 🧠 Analyse")
    st.write(result.get("analysis", "N/A"))

    st.markdown("### 🔗 Sources")
    for src in result.get("sources", []):
        st.write(f"- {src}")

# =========================================================
# EMPTY STATE
# =========================================================
if not launch:
    st.info("Saisissez une requête et lancez la recherche.")