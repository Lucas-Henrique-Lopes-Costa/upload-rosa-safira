#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Baixa 5 imagens (verticais, alta qualidade) por produto da planilha dados.csv,
recorta no formato 744x744 (largura) x 940 (altura) em modo "cover" e salva
em pastas individuais dentro do Google Drive.

A planilha é atualizada com STATUS_DOWNLOAD e QTD_IMAGENS para permitir
que o script seja interrompido e retomado de onde parou.
"""
import csv
import os
import re
import sys
import time
import logging
import shutil
from PIL import Image
from icrawler.builtin import BingImageCrawler

PROJECT_DIR = "/Users/lucashenrique/Projetos/Faculdade/upload rosa safira"
CSV_PATH = os.path.join(PROJECT_DIR, "dados.csv")
DEST_BASE = (
    "/Users/lucashenrique/Library/CloudStorage/"
    "GoogleDrive-lucashlc.contato@gmail.com/Meu Drive/"
    "Intensa Digital/3 - Operações/Materiais Projetos/Rosa Safira/Produtos"
)

TARGET_W = 744
TARGET_H = 940
NUM_IMAGES = 5
DOWNLOAD_MULT = 4   # baixa N x mais candidatas para filtrar as melhores
MIN_SRC_W = 500     # descarta imagens minúsculas
MIN_SRC_H = 500
PAUSE_BETWEEN = 1.5 # segundos entre produtos para não estressar o Bing


# termos genéricos que não ajudam (e atrapalham) a busca por imagens
NOISE_TERMS = {
    "PADRAO", "PADRÃO", "LISO", "ESTAMPADO", "ESTAMPADA",
    "LISO/ ESTAMPADO/PADRÃO", "ESTAMPADO/ LISO / PADRÃO",
    "ESTAMPADO/ LISO", "ESTAMPADO/LISO",
}


def _clean_term(term: str) -> str:
    """Normaliza um campo do CSV; descarta ruído e expande 'A/B' em 'A B'."""
    t = (term or "").strip().strip(",").strip()
    if not t or t.upper() in NOISE_TERMS:
        return ""
    parts = [p.strip() for p in t.split("/") if p.strip() and p.strip().upper() not in NOISE_TERMS]
    return " ".join(parts)


def build_keyword(desc: str, grupo: str, subgrupo: str, marca: str, cor: str) -> str:
    """Concatena DESCRIÇÃO + Grupo + Sub Grupo + Marca + Cor numa query enxuta."""
    parts = [desc.strip()]
    seen = {desc.strip().upper()}
    for extra in (grupo, subgrupo, marca, cor):
        cleaned = _clean_term(extra)
        if not cleaned:
            continue
        key = cleaned.upper()
        if key in seen:
            continue
        seen.add(key)
        parts.append(cleaned)
    return " ".join(parts)


def slugify(name: str) -> str:
    name = re.sub(r"[^\w\s\-]", "", name, flags=re.UNICODE).strip()
    name = re.sub(r"\s+", "_", name)
    return name[:80] or "produto"


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Redimensiona preenchendo w x h e cortando o excesso (CSS object-fit: cover)."""
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = w / h
    if src_ratio > target_ratio:
        new_h = h
        new_w = max(w, round(src_w * h / src_h))
    else:
        new_w = w
        new_h = max(h, round(src_h * w / src_w))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def score_image(img: Image.Image) -> float:
    """Pontuação simples: prioriza alta resolução e formato vertical."""
    w, h = img.size
    if w < MIN_SRC_W or h < MIN_SRC_H:
        return -1
    area_score = (w * h) / 1_000_000
    aspect = h / w if w else 0
    aspect_score = 1.0 if aspect >= 1 else 0.5
    return area_score + aspect_score


def process_folder(folder: str, num_keep: int = NUM_IMAGES) -> int:
    """Processa as imagens cruas baixadas: ranqueia, recorta cover, mantém as N melhores."""
    candidates = []
    for path in sorted(os.listdir(folder)):
        if path.startswith("."):
            continue
        full = os.path.join(folder, path)
        if not os.path.isfile(full):
            continue
        try:
            img = Image.open(full)
            img.load()
            if img.mode != "RGB":
                img = img.convert("RGB")
            s = score_image(img)
            if s < 0:
                os.remove(full)
                continue
            candidates.append((s, full, img))
        except Exception:
            try:
                os.remove(full)
            except OSError:
                pass

    candidates.sort(key=lambda c: c[0], reverse=True)

    kept = 0
    for idx, (_score, src_path, img) in enumerate(candidates):
        if kept >= num_keep:
            try:
                os.remove(src_path)
            except OSError:
                pass
            continue
        try:
            out = fit_cover(img, TARGET_W, TARGET_H)
            kept += 1
            new_name = f"{kept:02d}.jpg"
            new_path = os.path.join(folder, new_name)
            tmp_path = new_path + ".tmp"
            out.save(tmp_path, "JPEG", quality=92, optimize=True)
            os.replace(tmp_path, new_path)
        except Exception as e:
            print(f"    falha processando: {e}")
            kept -= 1
        finally:
            if src_path != new_path and os.path.exists(src_path):
                try:
                    os.remove(src_path)
                except OSError:
                    pass
    return kept


def download_for(keyword: str, folder: str) -> None:
    os.makedirs(folder, exist_ok=True)
    crawler = BingImageCrawler(
        storage={"root_dir": folder},
        log_level=logging.ERROR,
        downloader_threads=4,
    )
    crawler.crawl(
        keyword=keyword,
        max_num=NUM_IMAGES * DOWNLOAD_MULT,
        min_size=(MIN_SRC_W, MIN_SRC_H),
        filters={"type": "photo", "layout": "tall", "size": "large"},
    )


def read_csv_rows():
    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        return list(csv.reader(f))


def write_csv_rows(rows):
    tmp = CSV_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    os.replace(tmp, CSV_PATH)


def ensure_status_columns(rows):
    header = rows[0]
    if "STATUS_DOWNLOAD" not in header:
        header.append("STATUS_DOWNLOAD")
    if "QTD_IMAGENS" not in header:
        header.append("QTD_IMAGENS")
    return header.index("STATUS_DOWNLOAD"), header.index("QTD_IMAGENS")


def col_index(header, *targets) -> int | None:
    for i, c in enumerate(header):
        norm = c.strip().upper().rstrip(".")
        if norm in targets:
            return i
    return None


def get_cell(row, idx, default=""):
    return row[idx] if idx is not None and idx < len(row) else default


def set_cell(row, idx, value):
    while len(row) <= idx:
        row.append("")
    row[idx] = value


def main():
    if not os.path.isfile(CSV_PATH):
        sys.exit(f"CSV não encontrado: {CSV_PATH}")
    if not os.path.isdir(DEST_BASE):
        os.makedirs(DEST_BASE, exist_ok=True)

    rows = read_csv_rows()
    if len(rows) < 2:
        sys.exit("CSV sem linhas de dados")

    status_idx, qtd_idx = ensure_status_columns(rows)
    write_csv_rows(rows)  # persiste header novo

    header = rows[0]
    desc_idx = col_index(header, "DESCRIÇÃO", "DESCRICAO")
    ref_idx = col_index(header, "REF")
    grupo_idx = col_index(header, "GRUPO")
    subgrupo_idx = col_index(header, "SUB GRUPO", "SUBGRUPO")
    marca_idx = col_index(header, "MARCA/ FORNEC", "MARCA/FORNEC", "MARCA")
    cor_idx = col_index(header, "COR")
    if desc_idx is None:
        sys.exit("Coluna DESCRIÇÃO não encontrada")

    data_rows = rows[1:]
    total = sum(1 for r in data_rows if get_cell(r, desc_idx).strip())
    done = 0

    for i, row in enumerate(data_rows, start=1):
        desc = get_cell(row, desc_idx).strip()
        if not desc:
            continue
        done += 1
        ref = get_cell(row, ref_idx).strip()
        status = get_cell(row, status_idx).strip().upper()
        qtd = get_cell(row, qtd_idx).strip()

        if status == "OK" and qtd.isdigit() and int(qtd) >= NUM_IMAGES:
            print(f"[{done}/{total}] PULAR  {desc!r} (já tem {qtd} imagens)")
            continue

        folder_name = f"{ref}_{slugify(desc)}" if ref else slugify(desc)
        folder = os.path.join(DEST_BASE, folder_name)

        # limpa qualquer download anterior incompleto
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                try:
                    os.remove(os.path.join(folder, f))
                except OSError:
                    pass

        keyword = build_keyword(
            desc,
            get_cell(row, grupo_idx),
            get_cell(row, subgrupo_idx),
            get_cell(row, marca_idx),
            get_cell(row, cor_idx),
        )
        print(f"[{done}/{total}] BAIXAR {keyword!r} -> {folder_name}")
        try:
            download_for(keyword, folder)
            kept = process_folder(folder)
            set_cell(row, status_idx, "OK" if kept >= NUM_IMAGES else "PARCIAL")
            set_cell(row, qtd_idx, str(kept))
            print(f"           -> {kept} imagens 744x940 salvas")
        except KeyboardInterrupt:
            print("\nInterrompido pelo usuário — progresso salvo.")
            write_csv_rows(rows)
            sys.exit(130)
        except Exception as e:
            print(f"           ERRO: {e}")
            set_cell(row, status_idx, "ERRO")
            set_cell(row, qtd_idx, "0")
        finally:
            write_csv_rows(rows)
            time.sleep(PAUSE_BETWEEN)

    print("\nConcluído.")


if __name__ == "__main__":
    main()
