import io
import requests
import pandas as pd
import re

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
    }

    df_ban = df_ban.rename(columns=rename_map)

    # On garde les colonnes utiles
    df_ban = df_ban[[
        "adresse",
        "lat_BAN",
        "lon_BAN",
        "score_BAN",
        "adresse_BAN"
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

    print("df_loc")
    print(df_loc)
    print("Fin de la requête")

    return df_loc
