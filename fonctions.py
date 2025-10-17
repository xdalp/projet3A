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
        date_int = int(os.path.basename(path).split("_")[0])
        print(date_int)
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

    return gdf