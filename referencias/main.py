#!/usr/bin/env python
# -*- coding: utf-8 -*-

from icrawler.builtin import BingImageCrawler
import os

def download_images(keyword, max_num=5):
    # Cria um diretório para salvar as imagens caso não exista
    save_dir = os.path.join("images", keyword.replace(" ", "_"))
    os.makedirs(save_dir, exist_ok=True)
    
    # Configura e inicia o crawler do Bing Images
    crawler = BingImageCrawler(storage={'root_dir': save_dir})
    crawler.crawl(keyword=keyword, max_num=max_num)

def main():
    # Lê o arquivo keywords.txt e extrai as palavras (ignorando linhas vazias)
    with open("keywords.txt", "r", encoding="utf-8") as file:
        keywords = [line.strip() for line in file if line.strip()]
    
    # Verifica se há palavras para buscar
    if not keywords:
        print("Nenhuma palavra-chave encontrada no arquivo keywords.txt.")
        return

    # Cria o diretório principal para as imagens, se ainda não existir
    os.makedirs("images", exist_ok=True)
    
    # Para cada palavra-chave, baixa as 10 imagens do Google
    for keyword in keywords:
        print(f"Baixando imagens para: {keyword}")
        download_images(keyword)
        print(f"Concluído para: {keyword}\n")

if __name__ == "__main__":
    main()
