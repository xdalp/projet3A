# Ce code télécharge et stocke les données DB TOPO sur Onyxia

import requests
from bs4 import BeautifulSoup
import re
import os
from fonctions import download_to_SSPCloud

url_BDTOPO = "https://geoservices.ign.fr/bdtopo"

#extraction de la page
request_text = requests.get(url_BDTOPO).content
request_text

page = BeautifulSoup(request_text, "html.parser")
page

cle="Tous Thèmes par département format Shapefile projection légale"
h3_tags = page.find_all("h3")
h3_tags = [h3 for h3 in h3_tags if cle in h3.get_text()]

annees = list(range(2008, 2026))  # 2008 à 2025 inclus
mois = ["janvier", "février", "mars", "avril"] #on ne garde que les données T1 (par défaut = archive IGN)

h3_par_annee = {}

#extraction T1 h3 par année
for annee in annees:

    h3_annee = [h3 for h3 in h3_tags if str(annee) in h3.get_text()]
    if not h3_annee:
        continue  

    h3_selectionne = None
    for h3 in h3_annee:
        texte = h3.get_text().lower()
        if any(m in texte for m in mois):
            h3_selectionne = h3
            break
    
    if h3_selectionne is None:
        h3_selectionne = h3_annee[0]
    
    h3_par_annee[annee] = h3_selectionne


dep = re.compile(r"D0([0-8][0-9]|9[0-5])")

href_par_annee = {}

for annee, h3 in h3_par_annee.items():
    href_list = []
    for sibling in h3.find_next_siblings():
        if sibling.name == "h3":
            break
        if sibling.name == "ul":
            for li in sibling.find_all("li"):
                if dep.search(li.get_text()):
                    a_tag = li.find("a")
                    if a_tag and a_tag.get("href"):
                        href_list.append(a_tag["href"])
    href_par_annee[annee] = href_list

print(href_par_annee[2008])

href_par_annee={}
href_par_annee={2025:["https://data.geopf.fr/telechargement/download/BDTOPO/BDTOPO_3-3_TOUSTHEMES_GPKG_LAMB93_D092_2024-03-15/BDTOPO_3-3_TOUSTHEMES_GPKG_LAMB93_D092_2024-03-15.7z"]}

#ENREGISTREMENT DES DONNEES SUR ONYXIA
user = "onyxia"
base_path=f"{user}/diffusion/"

for annee, urls in href_par_annee.items():
    for url in urls:
        # Extraire DXXX depuis l'URL
        match = dep.search(url)
        if match:
            dxxx = match.group(1)
        else:
            dxxx = "unknown"

        # Extraire l'extension du fichier
        ext = url.split(".")[-1]

        sspcloud_path = f"{base_path}{annee}_{dxxx}.{ext}"

        # Télécharger le fichier sur SSP Cloud
        download_to_SSPCloud(url, sspcloud_path)