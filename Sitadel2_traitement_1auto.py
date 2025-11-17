#TRAITEMENT AUTOMATIQUE DE SITADEL2
import os
import pandas as pd
from credentials import s3
import requests
import io
import time

##################
#IMPORT DEPUIS ONYXIA
###################
path = "Sitadel/autorisations_locaux_2013_oct_2025.csv"
tmp = f"/tmp/{os.path.basename(path)}"

s3.download_file("mgarbe", path, tmp)
df = pd.read_csv(tmp, sep=";")

#####################
#TRAITEMENT BASIQUE + FILTRE
#########################
start_time = time.time()  # début du chrono


dest_map = {
    "Entrepôt",
    "Industrie",
    "Commerce"
}

patterns = [
    "Surface de plancher de la destination {} existante avant travaux",
    "Surface de plancher de la destination {} nouvelle construite",
    "Surface de plancher de la destination {} issue d'une transformation",
    "Surface de plancher de la destination {} démolie",
    "Surface de plancher de la destination {} transformée"
]

rename_static = [
    "Code du département du lieu des travaux - Code de la zone",
    "Code de la région du lieu des travaux - Code de la zone",
    "Code de la commune du lieu des travaux",
    "Date réelle d'autorisation (PC) ou de non-opposition (DP) initiale",
    "Date réelle d'ouverture de chantier",
    "Date réelle d'achèvement des travaux",
    "Nature du projet déclarée par le demandeur",
    "Indicateur d'extension",
    "Destination principale",
    'Numéro de voie du terrain',
    'Type de voie du terrain',
    'Libellé de la voie du terrain',
    'Lieu-dit du terrain',
    'Localité du terrain',
    'Code postal du terrain',
    'Superficie du terrain'
]

cols_dyn = []
for dest in dest_map:
    for pat in patterns:
        cols_dyn.append(pat.format(dest))

colonnes_a_garder = rename_static + cols_dyn
colonnes_existantes = [c for c in colonnes_a_garder if c in df.columns]

df = df[colonnes_existantes].copy()
df.columns = df.iloc[0].values
df = df.iloc[1:].reset_index(drop=True)

df["DEP_CODE"] = pd.to_numeric(df["DEP_CODE"], errors="coerce").astype("Int64") #CODE DEP EN INT
df = df[df["DEP_CODE"].notna() & (df["DEP_CODE"] < 96)] #SELECTION METROPOLE
df = df[df["DESTINATION_PRINCIPALE"].isin([4, 6, 8])] #SELECTION INDU, COMM, LOGISTIQUE


#selection surface brute crée >1000m2
cols = [f"SURF_{i}_CREEE" for i in ["ENT", "COM", "IND"]]
df[cols] = df[cols].apply(pd.to_numeric, errors="coerce").astype("Int64")
df1000 = df[
    (df[cols[0]] > 1000) |
    (df[cols[1]] > 1000) |
    (df[cols[2]] > 1000)
]



################
# LOCALISATION DES ADRESSES AVEC API BAN
#################

#df1000=df1000.head(1000).copy() #pour test

print(f"Longueur df :{len(df1000)}")

#conversion code postal en string 
df1000["ADR_CODPOST_TER"] = (
    pd.to_numeric(df1000["ADR_CODPOST_TER"], errors="coerce") 
    .astype("Int64")                                          
    .astype(str)                                              
    .str.zfill(5)
)                                             


#Construire la colonne adresse
df1000["adresse"] = (
    df1000["ADR_NUM_TER"].fillna("").astype(str) + " " +
    df1000["ADR_TYPEVOIE_TER"].fillna("").astype(str) + " " +
    df1000["ADR_LIBVOIE_TER"].fillna("").astype(str) + " " +
    df1000["ADR_LIEUDIT_TER"].fillna("").astype(str) + " " +
    df1000["ADR_LOCALITE_TER"].fillna("").astype(str) + " " +
    df1000["ADR_CODPOST_TER"].fillna("").astype(str)
).str.strip().str.replace(r"\s+", " ", regex=True)


#csv minimal
df_export = df1000[["adresse"]].copy()
csv_bytes = df_export.to_csv(index=False).encode("utf-8")


#appel unique de masse
url = "https://api-adresse.data.gouv.fr/search/csv/"

print("Envoi du CSV à l'API BAN")

response = requests.post(
    url,
    files={"data": ("adresses.csv", csv_bytes, "text/csv")},
    timeout=60
)

print("Réponse reçue, chargement…")

#Récupérer le CSV résultat dans un DataFrame
df1000_BAN = pd.read_csv(io.BytesIO(response.content))


#Renommer les colonnes importantes
df1000_BAN = df1000_BAN.rename(columns={
    "latitude": "lat_BAN",
    "longitude": "lon_BAN",
    "result_score": "score_BAN",
    "result_label": "adresse_BAN",
})

df1000_BAN = df1000_BAN[[
    "adresse",
    "lat_BAN",
    "lon_BAN",
    "score_BAN",
    "adresse_BAN"
]]

#on ne garde que le matching avec le meilleur score (si pas de num de rue, on a plusieurs entrées)
df1000_BAN=df1000_BAN.sort_values("score_BAN", ascending=False).drop_duplicates(subset="adresse")

#Fusion des résultats sur l’adresse
df1000 = df1000.merge(df1000_BAN, on="adresse", how="left")

print("Géocodage massif terminé.")

print(f"{df1000['lat_BAN'].isna().sum()}/{len(df1000)} adresses ne sont pas localisées.")



#tps 
end_time = time.time()  # fin du chrono
elapsed = end_time - start_time
print(f"Temps d'exécution : {elapsed:.2f} secondes")