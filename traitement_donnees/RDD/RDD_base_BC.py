import pandas as pd
import importlib
import credentials
importlib.reload(credentials)
import os 


#IDENTIFIANTS COMMUNES RDD
#on récupère les id_communes du RDD enregistrés en csv depuis le script
id_communes = pd.read_csv("id_communes.csv",sep=";")
id_communes['ann'] = id_communes['election'].map({
    '2014_muni': 2014,
    '2020_muni': 2020
})

id_communes['ann_BC'] = id_communes['election'].map({
    '2014_muni': 2011,
    '2020_muni': 2016
})


files_BC=credentials.s3.list_objects_v2(Bucket="mgarbe", Prefix="Elections/")["Contents"]

dfs = {}  # dictionnaire pour stocker les DataFrames

for f in files_BC:
    fname = os.path.basename(f["Key"])
    if fname.startswith("BC_") and fname.endswith(".csv"):
        # Nom après BC_
        suffix = fname[len("BC_"):-len(".csv")]
        local_path = f"/tmp/{fname}"
        
        # Télécharger le fichier
        credentials.s3.download_file("mgarbe", f["Key"], local_path)
        
        # Lire CSV
        dfs[f"df_{suffix}"] = pd.read_csv(local_path, sep=None, engine="python")

list(dfs.keys())


#merge densité OBS TERR
id_communes_BC = dfs["df_densite"][['an','codgeo','dens_pop']].merge(
    id_communes,
    left_on=["codgeo", "an"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['codgeo', 'an'])

#merge taux emploi OBS TERR
id_communes_BC = dfs["df_taux_emploi"][['an','codgeo','emp2064']].merge(
    id_communes_BC,
    left_on=["codgeo", "an"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['codgeo', 'an'])
id_communes_BC = id_communes_BC.rename(columns={'emp2064': 'taux_emploi'})

#merge taux emploi OBS TERR
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


#merge pop INSEE
id_communes_BC = dfs["df_pop"][['GEO','TIME_PERIOD','OBS_VALUE']].merge(
    id_communes_BC,
    left_on=["GEO", "TIME_PERIOD"],
    right_on=["Code INSEE", "ann_BC"],
    how="right"
).copy()
id_communes_BC = id_communes_BC.drop(columns=['GEO', 'TIME_PERIOD'])
id_communes_BC = id_communes_BC.rename(columns={'OBS_VALUE': 'pop'})


#homogeneisation types colonnes
id_communes_BC=id_communes_BC.drop(columns=["ann","ann_BC"])
colonnes_a_convertir = id_communes_BC.columns.drop(['election','Code INSEE'])
id_communes_BC[colonnes_a_convertir] = id_communes_BC[colonnes_a_convertir]\
    .astype(str)\
    .apply(lambda x: x.str.replace(',', '.'))\
    .apply(pd.to_numeric, errors='coerce')
print("id_communes_BC est disponible")

