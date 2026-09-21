"""Integração com a Serper.dev Places API (Google Maps) + filtros de qualificação de leads."""
import re

import requests

SERPER_PLACES_URL = "https://google.serper.dev/places"
RAW_RESULTS_TARGET = 50  # quantidade máxima de estabelecimentos buscados por pesquisa
RESULTS_PER_PAGE = 20  # tamanho de página retornado pela Serper
MAX_PAGES = 3  # 3 x 20 = até 60 resultados brutos, suficiente para cobrir os 50 pedidos


def _clean_phone(raw_phone: str) -> str:
    """Normaliza o telefone para dígitos puros com DDI 55 (Brasil)."""
    if not raw_phone:
        return ""
    digits = re.sub(r"\D", "", raw_phone)
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    if len(digits) in (10, 11):  # DDD + número, sem DDI
        return "55" + digits
    return digits


def whatsapp_link(telefone: str) -> str:
    digits = _clean_phone(telefone)
    return f"https://wa.me/{digits}" if digits else ""


REQUEST_TIMEOUT = 35  # segundos; a Serper.dev pode demorar em buscas com muitos resultados
PAGE_RETRIES = 2  # tentativas por página antes de desistir dela


def _fetch_page(payload: dict, headers: dict) -> list[dict] | None:
    """Busca uma página, tentando novamente em caso de timeout/erro de rede.
    Retorna None se todas as tentativas falharem (em vez de propagar a exceção)."""
    for attempt in range(PAGE_RETRIES):
        try:
            response = requests.post(
                SERPER_PLACES_URL, json=payload, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json().get("places", [])
        except requests.exceptions.RequestException:
            if attempt == PAGE_RETRIES - 1:
                return None
    return None


def search_places(nicho: str, cidade: str, api_key: str) -> list[dict]:
    """Busca estabelecimentos na Serper.dev Places API, paginando até atingir
    o alvo de resultados brutos ou esgotar as páginas disponíveis.

    Se uma página falhar mesmo após retentativas, a busca é encerrada e o que já
    foi coletado até ali é retornado, em vez de derrubar a pesquisa inteira."""
    if not api_key:
        raise ValueError("Informe a chave de API da Serper.dev na barra lateral.")

    query = f"{nicho} em {cidade}"
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    raw_results: list[dict] = []

    for page in range(1, MAX_PAGES + 1):
        payload = {"q": query, "gl": "br", "hl": "pt-br", "page": page}
        places = _fetch_page(payload, headers)

        if places is None:
            if not raw_results:
                raise ConnectionError(
                    "A Serper.dev não respondeu a tempo. Tente novamente em alguns segundos."
                )
            break  # mantém os resultados já coletados nas páginas anteriores
        if not places:
            break
        raw_results.extend(places)
        if len(raw_results) >= RAW_RESULTS_TARGET:
            break

    return raw_results[:RAW_RESULTS_TARGET]


def _has_no_website(place: dict) -> bool:
    website = (place.get("website") or "").strip()
    return website == ""


def _has_enough_reviews(place: dict, minimo: int = 10) -> bool:
    total = place.get("ratingCount") or place.get("reviews") or 0
    try:
        return int(total) >= minimo
    except (TypeError, ValueError):
        return False


def filter_and_map_leads(raw_places: list[dict], nicho: str, cidade: str) -> list[dict]:
    """Aplica os critérios de qualificação (sem site + >=10 avaliações) e
    converte cada resultado bruto no formato usado pela tabela `leads`."""
    leads = []
    for place in raw_places:
        if not _has_no_website(place):
            continue
        if not _has_enough_reviews(place):
            continue

        place_id = place.get("cid") or place.get("placeId") or place.get("fid") or place.get("title", "")
        telefone = _clean_phone(place.get("phoneNumber", ""))

        leads.append(
            {
                "place_id_google": str(place_id),
                "nome": place.get("title", "Sem nome"),
                "cidade": cidade,
                "nicho": nicho,
                "endereco": place.get("address", ""),
                "telefone": telefone,
                "email": "",  # Google Places não expõe e-mail; preencher manualmente após contato
                "redes_sociais": "",  # idem: sem site, não há fonte automática de redes sociais
                "rating": place.get("rating"),
                "total_reviews": place.get("ratingCount") or place.get("reviews"),
            }
        )
    return leads


def qualification_stats(raw_places: list[dict]) -> dict:
    """Detalha quantos resultados brutos foram descartados por cada critério,
    para explicar por que a lista final de leads qualificados é menor que o total buscado."""
    total = len(raw_places)
    com_site = sum(1 for p in raw_places if not _has_no_website(p))
    poucas_reviews = sum(
        1 for p in raw_places if _has_no_website(p) and not _has_enough_reviews(p)
    )
    qualificados = sum(
        1 for p in raw_places if _has_no_website(p) and _has_enough_reviews(p)
    )
    return {
        "total_bruto": total,
        "descartados_com_site": com_site,
        "descartados_poucas_reviews": poucas_reviews,
        "qualificados": qualificados,
    }


def search_and_filter_leads(nicho: str, cidade: str, api_key: str) -> list[dict]:
    raw_places = search_places(nicho, cidade, api_key)
    return filter_and_map_leads(raw_places, nicho, cidade)
