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