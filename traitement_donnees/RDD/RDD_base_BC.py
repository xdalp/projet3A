'''
Ce code ajoute à RDD_base_main des variables pour BC
'''

import pandas as pd
from functions.s3_connexion import get_s3
import os
from functions.basic_functions import upload_to_onyxia

#IDENTIFIANTS COMMUNES RDD
#on récupère les id_communes du RDD enregistrés en csv depuis le script
remote_path="RDD/df_RDD_main.csv"
local_path = f"/tmp/{os.path.basename(remote_path)}"
get_s3().download_file("mgarbe", remote_path, local_path)
df_RDD_main=pd.read_csv(local_path, sep=";")
id_communes=df_RDD_main[['election','Code INSEE']].copy()


id_communes['ann'] = id_communes['election'].map({
    '2014_muni': 2014,
    '2020_muni': 2020
})

id_communes['ann_BC'] = id_communes['election'].map({
    '2014_muni': 2011,
    '2020_muni': 2016
})

files_BC=get_s3().list_objects_v2(Bucket="mgarbe", Prefix="Elections/")["Contents"]

dfs = {}  # dictionnaire pour stocker les DataFrames

for f in files_BC:
    fname = os.path.basename(f["Key"])
    if fname.startswith("BC_") and fname.endswith(".csv"):
        # Nom après BC_
        suffix = fname[len("BC_"):-len(".csv")]
        local_path = f"/tmp/{fname}"
        
        # Télécharger le fichier
        get_s3().download_file("mgarbe", f["Key"], local_path)
        
        # Lire CSV
        dfs[f"df_{suffix}"] = pd.read_csv(local_path, sep=None, engine="python")

list(dfs.keys())


#[ajout variable] merge densité OBS TERR
id_communes_BC = dfs["df_densite"][['an','codgeo','dens_pop']].merge(
    id_communes,
    left_on=["codgeo", "an"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['codgeo', 'an'])
id_communes_BC = id_communes_BC.rename(columns={'dens_pop': 'BC_dens_pop'})

#[ajout variable] merge taux emploi OBS TERR
id_communes_BC = dfs["df_taux_emploi"][['an','codgeo','emp2064']].merge(
    id_communes_BC,
    left_on=["codgeo", "an"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['codgeo', 'an'])
id_communes_BC = id_communes_BC.rename(columns={'emp2064': 'BC_taux_emploi'})

#[ajout variable] merge taux emploi OBS TERR
dfs["df_chom_2011"]=dfs["df_chom_2011"].drop(columns="Libellé")
dfs["df_chom_2016"]=dfs["df_chom_2016"].drop(columns="Libellé")
dfs["df_chom_2011"].columns=["codgeo","taux_chom"]
dfs["df_chom_2016"].columns=["codgeo","taux_chom"]
dfs["df_chom_2011"]["an"]=2011
dfs["df_chom_2016"]["an"]=2016

dfs["df_chom"]=pd.concat([dfs["df_chom_2011"],dfs["df_chom_2016"]])

id_communes_BC = dfs["df_chom"][['an','codgeo','taux_chom']].merge(
    id_communes_BC,
    left_on=["codgeo", "an"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['codgeo', 'an'])
id_communes_BC = id_communes_BC.rename(columns={'taux_chom': 'BC_taux_chom'})

#[ajout variable] merge pop INSEE
id_communes_BC = dfs["df_pop"][['GEO','TIME_PERIOD','OBS_VALUE']].merge(
    id_communes_BC,
    left_on=["GEO", "TIME_PERIOD"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['GEO', 'TIME_PERIOD'])
id_communes_BC = id_communes_BC.rename(columns={'OBS_VALUE': 'BC_pop'})


#[cleaning] homogeneisation types colonnes
id_communes_BC=id_communes_BC.drop(columns=["ann","ann_BC"])
colonnes_a_convertir = id_communes_BC.columns.drop(['election','Code INSEE'])
id_communes_BC[colonnes_a_convertir] = id_communes_BC[colonnes_a_convertir]\
    .astype(str)\
    .apply(lambda x: x.str.replace(',', '.'))\
    .apply(pd.to_numeric, errors='coerce')
print("id_communes_BC est disponible")


#[cleaning] fusion avec df_RDD_BC.csv
df_RDD_main_BC_full=df_RDD_main.merge(
    id_communes_BC,
    left_on=["Code INSEE", "election"],
    right_on=["Code INSEE", "election"],
    how="left"
).copy()


#[upload onyxia]
output_file = "df_RDD_main_BC_full.csv"
df_RDD_main_BC_full.to_csv(output_file, index=False, sep=";")
remote_path = f"RDD/{output_file}"
upload_to_onyxia(output_file, bucket="mgarbe", remote_path=remote_path)
os.remove(output_file)
