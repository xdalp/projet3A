import os 
import pandas as pd
from functions.s3_connexion import get_s3
from functions.basic_functions import load_gpkg, upload_to_onyxia

########### IMPORTS #############

#données vote
remote_path="Elections/donnees_duel_maires_wide.csv"
local_path = f"/tmp/{os.path.basename(remote_path)}"
get_s3().download_file("mgarbe", remote_path, local_path)
df_vote=pd.read_csv(local_path, sep=",")
df_vote=df_vote[['id_election','rang1_Nuance','rang2_Nuance','rang1_voix_pct','rang2_voix_pct','election',
'tour','annee','dep_x','Nuance_interco','Code INSEE','Code Postal']].copy()

#codes nuances politiques
remote_path="Elections/nuances.csv"
local_path = f"/tmp/{os.path.basename(remote_path)}"
get_s3().download_file("mgarbe", remote_path, local_path)
nuances=pd.read_csv(local_path, sep=",")

#données géographiques
gdf=load_gpkg("Sitadel/df_clustering_fulldep_1000m3.gpkg") #SANS CLUSTER !!!
gdf=gdf[gdf["Base"]=="Sitadel"].copy()


########### RETRAITEMENT DES BASES #############

#[df_vote] codification des nuances
nuance_dict = pd.Series(nuances['Code'].values, index=nuances['Nuance']).to_dict()
df_vote['rang1_Nuance'] = df_vote['rang1_Nuance'].map(nuance_dict)
df_vote['rang2_Nuance'] = df_vote['rang2_Nuance'].map(nuance_dict)
df_vote['Nuance_interco'] = df_vote['Nuance_interco'].map(nuance_dict)

#[df_vote] filtre sur les paires (1,-1) et (-1,1), tous les 0 sont éliminés
df_vote = df_vote[
    (df_vote["rang1_Nuance"].abs() == 1) &
    (df_vote["rang2_Nuance"].abs() == 1) &
    (df_vote["rang1_Nuance"] != df_vote["rang2_Nuance"])
].copy()

#[df_vote] mesure de l'écart de score & identification des duels
df_vote['delta_score_1'] = df_vote['rang1_Nuance'] * (df_vote['rang1_voix_pct'] - df_vote['rang2_voix_pct'])
df_vote["duel"] = ((df_vote["rang1_voix_pct"] + df_vote["rang2_voix_pct"]) == 100).astype(int)

df_vote=df_vote[["election","Code INSEE","rang1_Nuance","delta_score_1","Nuance_interco"]].copy()


#[gdf] traitement gdf selon le mandat
def assign_mandat(annee):
    if 2014 <= annee <= 2019:
        return 2014  
    elif 2020 <= annee <= 2025:
        return 2020  
    else:
        return None   

gdf['mandat_elec'] = gdf['Annee_REF'].apply(assign_mandat)
gdf = gdf[gdf['mandat_elec'].notna()].copy()

#[gdf] normalisation gdf
gdf['COMM'] = gdf['COMM'].astype(str)
gdf.loc[gdf['COMM'].str.len() == 4, 'COMM'] = '0' + gdf.loc[gdf['COMM'].str.len() == 4, 'COMM']

#[gdf] summary des communes par mandat
gdf_summary = gdf.groupby(["mandat_elec", "COMM"]).agg(
    nb_permis=("SURF_CREEE", "count"),           # nombre de permis / lignes
    surface_creee=("SURF_CREEE", "sum"),        # somme de la surface créée
    surface_moyenne=("SURF_CREEE", "mean")     # surface moyenne par permis
).reset_index()
gdf_summary['mandat_elec'] = gdf_summary['mandat_elec'].astype(str) + '_muni'


############### FUSION ################


#[fusion] assure que les colonnes sont bien des strings
gdf_summary['COMM'] = gdf_summary['COMM'].astype(str)
df_vote['Code INSEE'] = df_vote['Code INSEE'].astype(str)

#[fusion] toutes les lignes de df_vote sont conservées
df_merged = df_vote.merge(
    gdf_summary,
    left_on=['Code INSEE', 'election'],
    right_on=['COMM', 'mandat_elec'],
    how='left'
)

cols_to_fill = ['nb_permis', 'surface_creee','surface_moyenne'] 
df_merged[cols_to_fill] = df_merged[cols_to_fill].fillna(0)

#[fusion] suppression de la colonne redondante
df_merged = df_merged.drop(columns=['COMM', 'mandat_elec']).copy()
gdf_summary=df_merged.copy()

#[upload onyxia]
output_file = "df_RDD_main.csv"
gdf_summary.to_csv(output_file, index=False, sep=";")
remote_path = f"RDD/{output_file}"
upload_to_onyxia(output_file, bucket="mgarbe", remote_path=remote_path)
os.remove(output_file)
