"""Sistema de captação e gestão de leads B2B (Streamlit + SQLite + Serper.dev Places API)."""
import sqlite3

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

import database as db
from api_client import filter_and_map_leads, qualification_stats, search_places, whatsapp_link

st.set_page_config(page_title="Captação de Leads B2B", page_icon="📇", layout="wide")
db.init_db()

# --------------------------------------------------------------------------- #
# Sidebar: configuração de API e formulário de busca
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("⚙️ Configuração")
    try:
        default_key = st.secrets.get("SERPER_API_KEY", "")
    except StreamlitSecretNotFoundError:
        default_key = ""
    api_key = st.text_input(
        "Chave de API (Serper.dev)",
        value=default_key,
        type="password",
        help="Crie uma chave gratuita em serper.dev. Também pode ser definida em .streamlit/secrets.toml",
    )

    st.divider()
    st.header("🔎 Nova Busca")
    with st.form("busca_form"):
        nicho = st.text_input("Nicho de Mercado", placeholder="Ex: Salão de beleza")
        cidade = st.text_input("Cidade/Estado", placeholder="Ex: Campinas, SP")
        buscar = st.form_submit_button("Buscar Leads (Até 50)", width="stretch")

    if buscar:
        if not nicho or not cidade:
            st.error("Preencha o nicho e a cidade/estado.")
        elif not api_key:
            st.error("Informe a chave de API da Serper.dev.")
        else:
            with st.spinner("Buscando e qualificando empresas..."):
                try:
                    raw_places = search_places(nicho, cidade, api_key)
                    stats = qualification_stats(raw_places)
                    leads = filter_and_map_leads(raw_places, nicho, cidade)

                    novos, duplicados = 0, 0
                    for lead in leads:
                        if db.insert_lead_if_new(lead):
                            novos += 1
                        else:
                            duplicados += 1

                    st.success(
                        f"Busca concluída: {len(leads)} leads qualificados encontrados "
                        f"({novos} novos, {duplicados} já existentes no banco)."
                    )
                    st.caption(
                        f"De {stats['total_bruto']} empresas encontradas no Google Maps: "
                        f"{stats['descartados_com_site']} já tinham site, "
                        f"{stats['descartados_poucas_reviews']} tinham menos de 10 avaliações, "
                        f"{stats['qualificados']} passaram nos dois filtros."
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Erro ao buscar leads: {exc}")

st.title("📇 Captação e Gestão de Leads B2B")

tab1, tab2, tab3 = st.tabs(
    ["🔍 Novas Pesquisas / Leads", "💾 Leads Salvos", "📤 Mensagens Enviadas"]
)


def render_lead_card(lead: sqlite3.Row, show_save_button: bool) -> None:
    """Renderiza o card de um lead com ações de WhatsApp, salvar e marcar como enviado."""
    with st.container(border=True):
        st.subheader(lead["nome"])
        st.write(f"📍 {lead['endereco'] or lead['cidade']}")
        st.write(f"🏷️ {lead['nicho']}")
        st.write(f"⭐ {lead['rating'] or '-'} ({lead['total_reviews'] or 0} avaliações)")
        st.write(f"📞 {lead['telefone'] or 'Telefone não disponível'}")
        if lead["email"]:
            st.write(f"✉️ {lead['email']}")
        if lead["redes_sociais"]:
            st.write(f"🌐 {lead['redes_sociais']}")

        botoes = st.columns(3 if show_save_button else 2)
        with botoes[0]:
            link = whatsapp_link(lead["telefone"])
            st.link_button(
                "📱 WhatsApp",
                link or "https://wa.me/",
                width="stretch",
                disabled=not link,
            )
        if show_save_button:
            with botoes[1]:
                if st.button("💾 Salvar", key=f"salvar_{lead['id']}", width="stretch"):
                    db.update_lead_status(lead["id"], db.STATUS_SALVO)
                    st.rerun()
            with botoes[2]:
                if st.button("✅ Enviada", key=f"enviado_{lead['id']}", width="stretch"):
                    db.update_lead_status(lead["id"], db.STATUS_ENVIADO)
                    st.rerun()
        else:
            with botoes[1]:
                if st.button("✅ Enviada", key=f"enviado_{lead['id']}", width="stretch"):
                    db.update_lead_status(lead["id"], db.STATUS_ENVIADO)
                    st.rerun()


# --------------------------------------------------------------------------- #
# Aba 1: leads novos da pesquisa, ainda não salvos nem contatados
# --------------------------------------------------------------------------- #
with tab1:
    novos_leads = db.get_leads_by_status([db.STATUS_NOVO])

    if not novos_leads:
        st.info("Nenhum lead novo no momento. Use a busca na barra lateral para encontrar empresas.")
    else:
        st.caption(f"{len(novos_leads)} lead(s) aguardando triagem.")
        cols = st.columns(2)
        for i, lead in enumerate(novos_leads):
            with cols[i % 2]:
                render_lead_card(lead, show_save_button=True)

# --------------------------------------------------------------------------- #
# Aba 2: leads salvos para contatar depois (não reaparecem em buscas futuras)
# --------------------------------------------------------------------------- #
with tab2:
    salvos = db.get_leads_by_status([db.STATUS_SALVO])

    if not salvos:
        st.info("Nenhum lead salvo. Use o botão 💾 Salvar na aba de novos leads.")
    else:
        st.caption(f"{len(salvos)} lead(s) salvos para contatar quando quiser.")
        cols = st.columns(2)
        for i, lead in enumerate(salvos):
            with cols[i % 2]:
                render_lead_card(lead, show_save_button=False)

# --------------------------------------------------------------------------- #
# Aba 3: leads já contatados
# --------------------------------------------------------------------------- #
with tab3:
    filtro_labels = ["Todos"] + [db.STATUS_LABELS[s] for s in db.STATUS_CONTATADOS]
    filtro = st.selectbox("Filtrar por status", filtro_labels)

    if filtro == "Todos":
        status_filtro = db.STATUS_CONTATADOS
    else:
        status_filtro = [k for k, v in db.STATUS_LABELS.items() if v == filtro]

    contatados = db.get_leads_by_status(status_filtro)

    if not contatados:
        st.info("Nenhum lead nesse status ainda.")
    else:
        st.caption(f"{len(contatados)} lead(s) encontrados.")
        df = pd.DataFrame(
            [
                {
                    "Empresa": lead["nome"],
                    "Cidade": lead["cidade"],
                    "Telefone": lead["telefone"],
                    "Status": db.STATUS_LABELS.get(lead["status"], lead["status"]),
                    "Contato em": lead["data_contato"] or "-",
                }
                for lead in contatados
            ]
        )
        st.dataframe(df, width="stretch", hide_index=True)

        st.divider()
        st.subheader("Atualizar lead")
        opcoes = {f"{lead['nome']} ({lead['cidade']})": lead["id"] for lead in contatados}
        escolha = st.selectbox("Selecione um lead", list(opcoes.keys()))
        lead_selecionado = next(l for l in contatados if l["id"] == opcoes[escolha])

        novo_status_label = st.selectbox(
            "Novo status",
            [db.STATUS_LABELS[s] for s in db.STATUS_CONTATADOS],
            index=db.STATUS_CONTATADOS.index(lead_selecionado["status"])
            if lead_selecionado["status"] in db.STATUS_CONTATADOS
            else 0,
        )
        observacoes = st.text_area("Observações", value=lead_selecionado["observacoes"] or "")

        if st.button("💾 Salvar alterações"):
            novo_status = next(k for k, v in db.STATUS_LABELS.items() if v == novo_status_label)
            db.update_lead_status(lead_selecionado["id"], novo_status, observacoes)
            st.success("Lead atualizado.")
            st.rerun()
