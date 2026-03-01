"""Utilitários de busca de materiais por SKU/nome com ranking fuzzy."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

from apps.inventory.models import Material


def parse_non_negative_int(raw_value, default: int = 0) -> int:
    """Converte valor em inteiro não negativo, com fallback padrão."""
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return max(value, 0)


def normalize_search_text(value: str) -> str:
    """Normaliza texto para comparação (casefold, sem acento e sem pontuação)."""
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = "".join(ch if (ch.isalnum() or ch.isspace()) else " " for ch in normalized)
    return " ".join(normalized.split()).strip()


def compact_search_text(value: str) -> str:
    """Versão compacta para comparar textos sem espaços."""
    return "".join(normalize_search_text(value).split())


def fuzzy_material_matches(query: str, materials_qs, limit: int | None = 20):
    """Retorna materiais ranqueados por similaridade com prioridade para match exato."""
    needle = normalize_search_text(query)
    if not needle:
        return []

    compact_needle = compact_search_text(query)
    needle_tokens = needle.split()
    ranked = []
    for material in materials_qs.only("id", "sku", "name", "unit").iterator():
        sku = normalize_search_text(material.sku)
        name = normalize_search_text(material.name)
        label = f"{sku} {name}".strip()
        compact_sku = compact_search_text(material.sku)
        compact_name = compact_search_text(material.name)
        compact_label = compact_search_text(label)

        base_ratio = max(
            SequenceMatcher(None, needle, sku).ratio(),
            SequenceMatcher(None, needle, name).ratio(),
            SequenceMatcher(None, needle, label).ratio(),
            SequenceMatcher(None, compact_needle, compact_sku).ratio(),
            SequenceMatcher(None, compact_needle, compact_name).ratio(),
            SequenceMatcher(None, compact_needle, compact_label).ratio(),
        )

        token_score = 0.0
        label_tokens = label.split()
        for token in label_tokens:
            token_score = max(token_score, SequenceMatcher(None, needle, token).ratio())

        partial_token_score = 0.0
        for n_token in needle_tokens:
            partial_token_score = max(
                partial_token_score, SequenceMatcher(None, n_token, sku).ratio()
            )
            partial_token_score = max(
                partial_token_score, SequenceMatcher(None, n_token, name).ratio()
            )
            for token in label_tokens:
                partial_token_score = max(
                    partial_token_score, SequenceMatcher(None, n_token, token).ratio()
                )

        score = max(base_ratio, token_score, partial_token_score)

        # Prioriza resultados que cobrem todos os termos da busca.
        all_tokens_in_name = bool(needle_tokens) and all(token in name for token in needle_tokens)
        all_tokens_in_label = bool(needle_tokens) and all(token in label for token in needle_tokens)
        phrase_in_name = needle in name
        phrase_in_label = needle in label
        compact_phrase_in_name = compact_needle and compact_needle in compact_name
        compact_phrase_in_label = compact_needle and compact_needle in compact_label

        if phrase_in_name:
            score = max(score, 1.4)
        elif phrase_in_label:
            score = max(score, 1.3)
        elif compact_phrase_in_name:
            score = max(score, 1.2)
        elif compact_phrase_in_label:
            score = max(score, 1.15)
        elif all_tokens_in_name:
            score = max(score, 1.1)
        elif all_tokens_in_label:
            score = max(score, 1.05)

        starts_with_priority = 1 if (name.startswith(needle) or sku.startswith(needle)) else 0
        ranked.append((score, starts_with_priority, material.sku, material))

    ranked.sort(key=lambda row: (-row[0], -row[1], row[2]))
    materials = [row[3] for row in ranked]
    if limit is None:
        return materials
    return materials[:limit]


def search_materials(query: str, offset_raw, limit_raw) -> tuple[list[Material], bool]:
    """Busca materiais com offset/limit e indica se há mais resultados."""
    offset = parse_non_negative_int(offset_raw, default=0)
    limit = parse_non_negative_int(limit_raw, default=20)
    if limit < 1:
        limit = 1
    limit = min(limit, 50)

    materials_qs = Material.objects.all().order_by("sku")

    if not query:
        materials = list(materials_qs[offset : offset + limit])
        has_more = materials_qs.count() > offset + len(materials)
    else:
        matched = fuzzy_material_matches(query, materials_qs, limit=None)
        materials = matched[offset : offset + limit]
        has_more = len(matched) > offset + len(materials)

    return materials, has_more
