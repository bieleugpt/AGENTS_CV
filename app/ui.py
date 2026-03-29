import importlib
import os
import sys

import streamlit as st


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config.settings as settings
from agent.orchestrator import run_agent, run_agent_with_prefetched_results
from tools.web.playwright_tool import PlaywrightTool

importlib.reload(settings)


st.set_page_config(
    page_title="AXA IA - Search Agent",
    layout="wide",
)

st.title("AXA IA - Intelligent Search Agent")
st.sidebar.header("Configuration")

mode = st.sidebar.selectbox(
    "Mode",
    ["Recherche", "Analyse incident"],
)

selected_sites = st.sidebar.multiselect(
    "Sources",
    settings.AVAILABLE_SITES,
    default=settings.AVAILABLE_SITES[:1],
)

interactive_mode = st.sidebar.checkbox(
    "Mode interactif web",
    key="interactive_mode_enabled",
    help="Ouvre un navigateur visible pour vous laisser valider la verification humaine avant de reprendre l'analyse.",
)

st.subheader("Recherche")

query = st.text_area(
    "Votre demande",
    placeholder="Ex: Developpeur Python remote CDI Paris",
)

launch = st.button("Lancer la recherche")
open_interactive = st.button(
    "Ouvrir la session interactive",
    disabled=not interactive_mode,
)
continue_interactive = st.button(
    "J'ai valide, continuer",
    disabled=not interactive_mode,
)
close_interactive = st.button(
    "Fermer la session interactive",
    disabled=not st.session_state.get("interactive_session_id"),
)

st.session_state.setdefault("interactive_session_id", None)
st.session_state.setdefault("interactive_source", None)
st.session_state.setdefault("last_result", None)

if interactive_mode:
    st.info(
        "Mode interactif actif. Utilisez `Ouvrir la session interactive`, "
        "validez la verification humaine dans le navigateur, puis cliquez sur "
        "`J'ai valide, continuer`."
    )


def render_result(result: dict) -> None:
    st.success("Resultat")
    st.markdown("### Resume")
    st.write(result.get("summary", "N/A"))

    st.markdown("### Donnees cles")
    st.write(result.get("data", "N/A"))

    st.markdown("### Problemes detectes")
    st.write(result.get("issues", "N/A"))

    st.markdown("### Analyse")
    st.write(result.get("analysis", "N/A"))

    st.markdown("### Sources")
    for src in result.get("sources", []):
        st.write(f"- {src}")

    report_files = result.get("report_files", {})
    if report_files:
        st.markdown("### Rapport")
        st.write(report_files)

    job_offers = result.get("job_offers", [])
    if job_offers:
        st.markdown("### Offres classees")
        min_score = st.slider("Score minimum", min_value=0, max_value=20, value=0, step=1)
        contracts = sorted({offer.get("contract", "") for offer in job_offers if offer.get("contract")})
        contract_filter = st.selectbox("Contrat", ["Tous"] + contracts)
        keyword_filter = st.text_input("Mot-cle filtre", value="")

        filtered_offers = []
        for offer in job_offers:
            if offer.get("score", 0) < min_score:
                continue
            if contract_filter != "Tous" and offer.get("contract") != contract_filter:
                continue
            if keyword_filter and keyword_filter.lower() not in str(offer).lower():
                continue
            filtered_offers.append(offer)

        st.dataframe(filtered_offers, width="stretch")

    st.markdown("### Resultats bruts par source")
    raw_results = result.get("raw_results", [])
    if raw_results:
        for item in raw_results:
            source_name = item.get("source", "source_inconnue")
            with st.expander(f"Source brute: {source_name}"):
                st.write(item)
    else:
        st.info("Aucun resultat brut disponible.")

    st.markdown("### Execution")
    st.write({
        "mode": result.get("mode"),
        "strategy": result.get("strategy"),
        "tools_used": result.get("tools_used"),
    })


def selected_web_source() -> str | None:
    if len(selected_sites) != 1:
        return None
    site = selected_sites[0]
    site_config = settings.SITE_CONFIGS.get(site, {})
    if site.startswith(("http://", "https://")) or site_config.get("type") == "web":
        return site
    return None


if open_interactive:
    st.session_state["last_result"] = None
    if not query:
        st.error("Saisissez une requete avant d'ouvrir une session interactive.")
    else:
        site = selected_web_source()
        if not site:
            st.error("Le mode interactif exige exactement une source web selectionnee.")
        else:
            web_tool = PlaywrightTool(headless=False)
            session_info = web_tool.start_interactive_session(query=query, site=site)
            if session_info.get("ok"):
                st.session_state["interactive_session_id"] = session_info["session_id"]
                st.session_state["interactive_source"] = site
                st.info(session_info["message"])
                st.write({"url": session_info.get("current_url"), "source": site})
            else:
                st.error(session_info["message"])

if continue_interactive:
    st.session_state["last_result"] = None
    session_id = st.session_state.get("interactive_session_id")
    source = st.session_state.get("interactive_source")

    if not session_id or not source:
        st.error("Aucune session interactive ouverte.")
    elif not query:
        st.error("Saisissez une requete avant de continuer.")
    else:
        web_tool = PlaywrightTool(headless=False)
        captured = web_tool.capture_interactive_session(session_id)

        if not captured.get("ok"):
            st.error(captured["message"])
        else:
            result = run_agent_with_prefetched_results(
                query=query,
                mode=mode,
                sources=[source],
                raw_results=[{
                    "source": captured["source"],
                    "source_kind": captured["source_kind"],
                    "status": captured["status"],
                    "content": captured["content"],
                }],
            )
            st.session_state["last_result"] = result
            render_result(result)

if close_interactive:
    session_id = st.session_state.get("interactive_session_id")
    if session_id:
        PlaywrightTool(headless=False).close_interactive_session(session_id)
    st.session_state["interactive_session_id"] = None
    st.session_state["interactive_source"] = None
    st.session_state["last_result"] = None
    st.info("Session interactive fermee.")

if launch and interactive_mode:
    st.warning(
        "Le mode interactif web est actif. Utilisez `Ouvrir la session interactive`, "
        "validez la verification humaine dans le navigateur, puis cliquez sur "
        "`J'ai valide, continuer`."
    )
elif launch and query:
    with st.spinner("Analyse en cours..."):
        try:
            result = run_agent(
                query=query,
                mode=mode,
                sources=selected_sites,
            )
        except Exception as exc:
            st.error(f"Erreur systeme: {str(exc)}")
            st.stop()

    st.session_state["last_result"] = result
    render_result(result)
elif st.session_state.get("last_result") is not None:
    render_result(st.session_state["last_result"])
else:
    st.info("Saisissez une requete et lancez la recherche.")
