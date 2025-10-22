
# FONCTIONS TELECHARGEMENT BDTOPO TO ONYXIA

import s3fs
import requests 
import time
import re


def download_to_SSPCloud(url, sspcloud_path, max_retries=5):
    """
    Télécharge un fichier depuis une URL et l'enregistre sur SSP Cloud via s3fs.
    
    Arguments :
    - url : str, l'URL du fichier à télécharger
    - sspcloud_path : str, chemin complet sur le SSP Cloud"
    """

    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    fs = s3fs.S3FileSystem(client_kwargs={"endpoint_url": "https://minio.lab.sspcloud.fr"})

    # Création du dossier parent si nécessaire
    parent_folder = "/".join(sspcloud_path.split("/")[:-1])
    if not fs.exists(parent_folder):
        fs.mkdir(parent_folder, exist_ok=True)

    # Vérifie si le fichier existe déjà
    if fs.exists(sspcloud_path):
        print(f"[Ignoré] {sspcloud_path} existe déjà.")
        return
    
    attempt=0
    while attempt < max_retries:
        try:
            #print(f"Téléchargement: {url} → {sspcloud_path} (essai {attempt+1})")
            response = requests.get(url, stream=True, headers=headers)
            response.raise_for_status()
            
            # Écriture directement sur SSP Cloud
            with fs.open(sspcloud_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print("Téléchargement ok")
            return  # succès, on sort de la boucle
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait = 5 * (attempt + 1)  # pause progressive
                print(f"429 Too Many Requests. Attente {wait}s avant le prochain essai...")
                time.sleep(wait)
                attempt += 1
            else:
                raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Erreur lors du téléchargement de {url}: {e}")
            return
    print(f"Échec après {max_retries} tentatives pour {url}")




def test_archive_s3(s3_path, bucket="mgarbe"):
    """Télécharge un fichier .7z depuis S3 et vérifie s'il est corrompu."""
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, os.path.basename(s3_path))
            s3.download_file(bucket, s3_path, local_path)
            with py7zr.SevenZipFile(local_path, mode="r") as z:
                z.list()  # vérifie les headers
        return s3_path, False
    except Exception:
        return s3_path, True


def check_corrompu(paths, max_workers=10, bucket="mgarbe"):
    """
    Vérifie en parallèle (sur max_workers cœurs)
    si les fichiers .7z du bucket S3 sont corrompus.
    Retourne la liste des fichiers corrompus.
    """
    corrupted = []

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_archive_s3, p, bucket): p for p in paths}
        for future in as_completed(futures):
            path, is_corrupted = future.result()
            if is_corrupted:
                corrupted.append(path)

    return corrupted

import subprocess

def delete_from_onyxia(paths, bucket="mgarbe"):
    """
    Supprime les fichiers listés sur Onyxia dans le bucket SSPCloud.
    
    Args:
        paths (list of str): chemins complets des fichiers à supprimer.
        bucket (str): nom du bucket Onyxia.
    """
    if not paths:
        print("Aucun fichier à supprimer.")
        return

    for path in paths:
        # SSPCloud utilise généralement la commande 'rclone delete' ou 'mc rm'
        # Ici on suppose rclone, adapte si tu utilises mc ou autre.
        full_path = f"{bucket}/{path}"
        try:
            subprocess.run(["rclone", "delete", full_path], check=True)
            print(f"Supprimé : {full_path}")
        except subprocess.CalledProcessError as e:
            print(f"Erreur suppression {full_path} : {e}")




def upload_to_onyxia(local_path, bucket="mgarbe", remote_path="BDTOPO/BDTOPO_BATI_merge.gpkg"):
    """
    Envoie un fichier local sur le bucket Onyxia (S3) via boto3.
    """
    session = boto3.session.Session()
    s3 = session.client(
        service_name='s3',
        endpoint_url="https://minio.lab.sspcloud.fr",  # endpoint d’Onyxia
    )

    print(f"[Upload] Envoi de {local_path} vers {bucket}/{remote_path} ...")
    with open(local_path, "rb") as f:
        s3.upload_fileobj(f, bucket, remote_path)
    print("[Upload] Terminé")



# FONCTIONS TRAITEMENT DONNES



import boto3
import geopandas as gpd
import tempfile
import os
import py7zr 
import glob
from credentials import s3

def load_shapefile(path, bucket="mgarbe", region=""):
    """
    Récupère un shapefile depuis un bucket S3 et le charge dans un GeoDataFrame GeoPandas.
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_path = os.path.join(tmpdir, os.path.basename(path))
        # vérif d’accès
        try:
            s3.head_object(Bucket=bucket, Key=path)
        except s3.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "403":
                raise RuntimeError("Accès refusé : vos credentials AWS ont probablement expiré.")
            else:
                raise
        s3.download_file(bucket, path, archive_path)

        with py7zr.SevenZipFile(archive_path, mode='r') as archive: #décompression
            archive.extractall(path=tmpdir)
        base_name = os.path.splitext(os.path.basename(path))[0]
        parts = base_name.split("_")
        date_int = int(parts[0])
        dep = parts[1]
        if date_int < 2019:
             pattern = os.path.join(
                tmpdir,
                "BDTOPO*",
                "BDTOPO",
                "1_DONNEES*",
                "BDT*",
                "E_BATI",
                "BATI_INDUSTRIEL.SHP")
        else:
            pattern = os.path.join(
                tmpdir,
                "BDTOPO*",
                "BDTOPO",
                "1_DONNEES*",
                "BDT*",
                "BATI",
                "BATIMENT.shp"
            )

        shp_matches = glob.glob(pattern, recursive=True)

        if not shp_matches:
            raise FileNotFoundError(
                f"Aucun shapefile XXX.SHP trouvé dans la structure attendue ({pattern})"
            )

        shp_path = shp_matches[0]

        # Lecture du shapefile
        gdf = gpd.read_file(shp_path)

           # Ajout des colonnes 'annee' et 'departement'
        gdf["Annee"] = date_int
        gdf["Dep"] = dep

    return gdf

import boto3
from credentials import s3
def list_files_onyxia(bucket_name="mgarbe", prefix="BDTOPO/"):
    paginator = s3.get_paginator('list_objects_v2')
    files = []
    for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/'):
        for obj in page.get('Contents', []):
            if obj['Key'].endswith('.7z'):
                files.append(obj['Key'])

    return files



import geopandas as gpd

def filter_shapefile(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    2 versions du shapefile = 2 filtres 
    - v1 : filtre NATURE ∈ ['Bâtiment commercial', 'Bâtiment industriel']
    - v2 : filtre :
            NATURE == 'Industriel, agricole ou commercial'
            et USAGE1 ∈ ['Industriel', 'Commercial et services']
    """

    # Vérifie la présence de D pour déterminer la version
    is_v2 = "USAGE1" in gdf.columns
    vec=["Annee","Dep","ORIGIN_BAT", "NATURE", "USAGE1", "USAGE2","HAUTEUR","geometry","ETAT","DATE_CREAT","DATE_MAJ","ID_SOURCE","SOURCE"]
    cols_to_keep = [col for col in vec if col in gdf.columns]
    gdf = gdf[cols_to_keep].copy()
    
    if is_v2:
        gdf = gdf[(gdf["NATURE"] == "Industriel, agricole ou commercial")
            & (gdf["USAGE1"].isin(["Industriel", "Commercial et services"]))]
    else:
        gdf = gdf[gdf["NATURE"].isin(["Bâtiment commercial", "Bâtiment industriel"])]

    gdf = gdf.reset_index(drop=True)
    return gdf




import geopandas as gpd
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd

def process_file(path, bucket="mgarbe",target_crs="EPSG:2154"):
    """
    Charge + filtre un shapefile unique.
    """
    #print(f"[PID {os.getpid()}] Traitement {path}")
    gdf = load_shapefile(path, bucket=bucket)
    gdf_filtered = filter_shapefile(gdf)
    # conversion CRS si nécessaire
    if gdf_filtered.crs != target_crs:
        gdf_filtered = gdf_filtered.to_crs(target_crs)
    return gdf_filtered

import psutil


def parallel_process(all_paths, bucket="mgarbe", max_workers=None, target_crs="EPSG:2154", ram_limit_fraction=0.8, display_interval=15):
    """
    Charge les fichiers en parallèle et fusionne immédiatement chaque GDF dès qu'il est prêt,
    pour garder la pile (stack) petite et limiter la mémoire utilisée.
    Affiche des informations détaillées sur le traitement, la fusion et la mémoire.
    Affichage mémoire toutes les display_interval secondes avec % fichiers fusionnés.
    """
    stack = []
    total_ram_bytes = psutil.virtual_memory().total
    total_files = len(all_paths)
    processed_count = 0
    last_display = time.time()

    def current_ram_percent(additional_bytes=0):
        return (psutil.virtual_memory().used + additional_bytes) / total_ram_bytes * 100

    def merge_with_memory_check(gdf1, gdf2):
        """Fusionne deux GDF en vérifiant que la mémoire ne dépasse pas la limite."""
        additional_bytes = gdf1.memory_usage(deep=True).sum() + gdf2.memory_usage(deep=True).sum()
        ram_percent = current_ram_percent(additional_bytes)
        #print(f"[Fusion] Fusion de 2 GDF : mémoire approx. utilisée {ram_percent:.1f}%")
        if ram_percent > ram_limit_fraction * 100:
            raise MemoryError(f"Fusion dépasserait la limite RAM ({ram_percent:.1f}%)")
        merged = pd.concat([gdf1, gdf2], ignore_index=True, sort=False)
        return merged

    # Traitement des fichiers en parallèle
    with ProcessPoolExecutor(max_workers=max_workers or len(all_paths)) as executor:
        futures = {executor.submit(process_file, path, bucket, target_crs): path for path in all_paths}

        for future in as_completed(futures):
            path = futures[future]
            try:
                #print(f"[Décompression] {path}")
                gdf = future.result()
                gdf_mem = gdf.memory_usage(deep=True).sum()
                processed_count += 1

                # Fusion immédiate avec la pile
                if stack:
                    try:
                        merged = merge_with_memory_check(stack.pop(), gdf)
                        stack.append(merged)
                    except MemoryError as me:
                        print(me)
                        return None
                else:
                    stack.append(gdf)

                # Affichage toutes les display_interval secondes
                now = time.time()
                if now - last_display >= display_interval:
                    pct_fusion = processed_count / total_files * 100
                    ram_percent = current_ram_percent()
                    print(f"[Mémoire] {ram_percent:.1f}% utilisée, {pct_fusion:.1f}% fichiers traités")
                    last_display = now

            except Exception as e:
                print(f"[Erreur] sur {path} : {e}")

    # Résultat final
    if stack:
        full_gdf = stack[0]
        full_mem = full_gdf.memory_usage(deep=True).sum()
        ram_percent = current_ram_percent(full_mem)
        print(f"[Final] Fusion complète terminée : {len(full_gdf)} lignes, mémoire approx. {ram_percent:.1f}%")
        return full_gdf
    else:
        print("[Final] Aucun GDF traité, retour d'un GeoDataFrame vide")
        return gpd.GeoDataFrame()