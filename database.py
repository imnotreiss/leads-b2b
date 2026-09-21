"""Camada de acesso ao SQLite: schema, deduplicação e operações sobre leads."""
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "leads.db"

STATUS_NOVO = "novo"
STATUS_ENVIADO = "enviado"
STATUS_NEGOCIACAO = "negociacao"
STATUS_FECHADO = "fechado"
STATUS_SEM_RESPOSTA = "sem_resposta"
STATUS_DESCARTADO = "descartado"

STATUS_CONTATADOS = [
    STATUS_ENVIADO,
    STATUS_NEGOCIACAO,
    STATUS_FECHADO,
    STATUS_SEM_RESPOSTA,
    STATUS_DESCARTADO,
]

STATUS_LABELS = {
    STATUS_NOVO: "Novo",
    STATUS_ENVIADO: "Enviado",
    STATUS_NEGOCIACAO: "Em Negociação",
    STATUS_FECHADO: "Fechado",
    STATUS_SEM_RESPOSTA: "Sem Resposta",
    STATUS_DESCARTADO: "Descartado",
}


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            place_id_google TEXT UNIQUE,
            nome TEXT NOT NULL,
            cidade TEXT,
            nicho TEXT,
            endereco TEXT,
            telefone TEXT,
            email TEXT,
            redes_sociais TEXT,
            rating REAL,
            total_reviews INTEGER,
            status TEXT NOT NULL DEFAULT 'novo',
            observacoes TEXT,
            data_cadastro TEXT NOT NULL,
            data_contato TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def lead_exists(place_id: str, telefone: str) -> bool:
    conn = get_connection()
    query = "SELECT id FROM leads WHERE place_id_google = ?"
    params = [place_id]
    if telefone:
        query += " OR (telefone != '' AND telefone = ?)"
        params.append(telefone)
    row = conn.execute(query, params).fetchone()
    conn.close()
    return row is not None


def insert_lead_if_new(lead: dict) -> bool:
    """Insere o lead com status 'novo' se ele ainda não existir no banco
    (por place_id_google ou telefone). Retorna True se inseriu, False se era duplicado."""
    if lead_exists(lead.get("place_id_google", ""), lead.get("telefone", "")):
        return False

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO leads (
            place_id_google, nome, cidade, nicho, endereco, telefone, email,
            redes_sociais, rating, total_reviews, status, data_cadastro
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            lead.get("place_id_google"),
            lead.get("nome"),
            lead.get("cidade"),
            lead.get("nicho"),
            lead.get("endereco"),
            lead.get("telefone"),
            lead.get("email", ""),
            lead.get("redes_sociais", ""),
            lead.get("rating"),
            lead.get("total_reviews"),
            STATUS_NOVO,
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()
    return True


def get_leads_by_status(status_list: list[str]) -> list[sqlite3.Row]:
    conn = get_connection()
    placeholders = ",".join("?" for _ in status_list)
    rows = conn.execute(
        f"SELECT * FROM leads WHERE status IN ({placeholders}) ORDER BY data_cadastro DESC",
        status_list,
    ).fetchall()
    conn.close()
    return rows


def update_lead_status(lead_id: int, status: str, observacoes: str | None = None) -> None:
    conn = get_connection()
    if observacoes is not None:
        conn.execute(
            """
            UPDATE leads
            SET status = ?, observacoes = ?, data_contato = COALESCE(data_contato, ?)
            WHERE id = ?
            """,
            (status, observacoes, datetime.now().isoformat(timespec="seconds"), lead_id),
        )
    else:
        conn.execute(
            """
            UPDATE leads
            SET status = ?, data_contato = COALESCE(data_contato, ?)
            WHERE id = ?
            """,
            (status, datetime.now().isoformat(timespec="seconds"), lead_id),
        )
    conn.commit()
    conn.close()
