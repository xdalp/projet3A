import io
import requests
import pandas as pd
import re
import geopandas as gpd

def format_insee(code):
    if pd.isna(code):
        return code
    code_str = str(code).replace(",", ".").strip()  # enlever virgules ou espaces
    if code_str.isdigit():  # code purement numérique
        return code_str.zfill(5)
    else:  # code avec lettres, on laisse tel quel
        return code_str

def safe_str(x):
    """Convertit NaN en chaîne vide et strippe la valeur."""
    if pd.isna(x):
        return ""
    return str(x).strip()


def adress_cleaning(adresse):
    if not isinstance(adresse, str):
        return adresse
    # Liste des chaînes à supprimer
    patterns = ["ZI DU", "ZI DE", "ZI", "ZAC DU", "ZAC DE", "ZAC", 
                "ZA", "ZA DU","ZA DE","CEDEX",'"',"0<NA>","<NA>"]
    # Construire une regex qui supprime toutes les occurrences
    pattern = "|".join(map(re.escape, patterns))
    adresse = re.sub(pattern, "", adresse, flags=re.IGNORECASE)
    return adresse

def address(row, option=1):
    """Construit une adresse selon l'option choisie."""
    num = safe_str(row.get("ADR_NUM_TER", ""))
    type_voie = safe_str(row.get("ADR_TYPEVOIE_TER", ""))
    voie = safe_str(row.get("ADR_LIBVOIE_TER", ""))
    lieu = safe_str(row.get("ADR_LIEUDIT_TER", ""))
    localite = safe_str(row.get("ADR_LOCALITE_TER", ""))
    cp = safe_str(row.get("ADR_CODPOST_TER", ""))

    #Adresse complère pour requête 1 
    if option == 1:
        adresse = f"{num} {type_voie} {voie} {cp} {localite}"

    #Adresse pour requête 2
    elif option == 2:
        adresse = f"{num} {type_voie} {voie} {lieu} {cp} {localite}"
    elif option == 3 :
        adresse=adress_cleaning(f"{num} {type_voie} {voie} {cp} {localite}")
    else:
        raise ValueError("option doit être 1 ou 2.")

    # Nettoyage : supprime les doubles espaces
    adresse = " ".join(adresse.split())

    patterns = [r'\bparc\b', r'\bparc d activite\b', r'\bparc d\'activite\b', r'\bparc activite\b', r'\b\w*parc\w*\b']
    pattern = "|".join(patterns)
    adresse = re.sub(pattern, "ZA", adresse, flags=re.IGNORECASE)

    return adresse





def geocode(df, adresse_col="adresse"):
    """
    Géocodage massif via API Adresse BAN (endpoint /search/csv/).
    """
    print("Lancement de la requête BAN")

    # Extraction minimale
    df = df.rename(columns={adresse_col: "adresse"})
    df_export = df["adresse"].copy()
    csv_bytes = df_export.to_csv(index=False).encode("utf-8")

    url = "https://api-adresse.data.gouv.fr/search/csv/"

    response = requests.post(
        url,
        files={"data": ("adresses.csv", csv_bytes, "text/csv")},
        timeout=60
    )

    # Charger le CSV retourné
    df_ban = pd.read_csv(io.BytesIO(response.content))

    # Harmonisation des noms
    rename_map = {
        "latitude": "lat_BAN",
        "longitude": "lon_BAN",
        "result_score": "score_BAN",
        "result_label": "adresse_BAN",
        "result_citycode": "code_com_BAN"
    }

    df_ban = df_ban.rename(columns=rename_map)

    # On garde les colonnes utiles
    df_ban = df_ban[[
        "adresse",
        "lat_BAN",
        "lon_BAN",
        "score_BAN",
        "adresse_BAN",
        "code_com_BAN",
    ]]

    # Si plusieurs résultats, on garde le meilleur score
    df_ban = (
        df_ban
        .sort_values("score_BAN", ascending=False)
        .drop_duplicates(subset="adresse")
    )

    print("df_ban")
    print(df_ban)

    df_loc = df.merge(df_ban, on=adresse_col, how="left")
    df_loc["code_com_BAN"] = df_loc["code_com_BAN"].apply(format_insee)
    print("df_loc")
    print(df_loc)
    print("Fin de la requête")
    
    return df_loc



def reverse_geocode(temp):
    """
    Reverse geocode massif via CSV BAN.
    temp : GeoDataFrame avec colonnes lat_temp, lon_temp
    """
    # Reprojeter pour calcul correct des centroïdes
    temp_proj = temp.to_crs("EPSG:2154")
    centroids = temp_proj.geometry.centroid
    centroids_wgs = gpd.GeoSeries(centroids, crs="EPSG:2154").to_crs("EPSG:4326")
    temp["lat_temp"] = centroids_wgs.y
    temp["lon_temp"] = centroids_wgs.x

    # Préparer CSV minimal
    df_csv = temp[["lat_temp", "lon_temp"]].copy()
    df_csv = df_csv.rename(columns={"lat_temp": "lat", "lon_temp": "lon"})

    # Convertir en CSV bytes
    csv_bytes = df_csv.to_csv(index=False).encode("utf-8")
    files = {"data": ("coords.csv", csv_bytes, "text/csv")}
    data = {
        "lat": "lat",
        "lon": "lon",
        "result_columns": ["result_postcode", "result_city", "result_score","result_citycode"]
    }
    url = "https://api-adresse.data.gouv.fr/reverse/csv/"
    response = requests.post(url, files=files, data=data, timeout=120)

    # Lire le CSV retourné
    df_ban = pd.read_csv(io.BytesIO(response.content))
    print("df_ban")
    print(df_ban)
    # Renommer colonnes utiles
    rename_map = {
        "result_citycode": "CODE_COM_BDTOPO",
        "result_postcode":"CODE_POST_BDTOPO",
        "result_city": "COM_BDTOPO",
        "result_score": "score_BDTOPO"
    }
    df_ban = df_ban.rename(columns=rename_map)

    # Merge avec temp
    temp = temp.reset_index(drop=True)
    df_ban = df_ban.reset_index(drop=True)
    temp = pd.concat([temp, df_ban[["CODE_COM_BDTOPO", "CODE_POST_BDTOPO","COM_BDTOPO", "score_BDTOPO"]]], axis=1)
    for col in ["CODE_COM_BDTOPO", "CODE_POST_BDTOPO"]:
        temp[col] = temp[col].apply(lambda x: str(int(x)).zfill(5) if pd.notna(x) else x)
    return temp

