import s3fs
import requests 

def download_to_SSPCloud(url, sspcloud_path):
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
    

    try:
        #print(f"Téléchargement: {url} → {sspcloud_path}")
        response = requests.get(url, stream=True, headers=headers)#requests.get(url, stream=True)
        response.raise_for_status()
        
        # Écriture directement sur SSP Cloud
        with fs.open(sspcloud_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print("Téléchargement ok")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Erreur lors du téléchargement de {url}: {e}")