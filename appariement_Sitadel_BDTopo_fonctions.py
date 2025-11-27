import geopandas as gpd
import pandas as pd
from tqdm import tqdm

def run_batch(gdf, batch, batch_num, queue, annee_min=2014, rayon=10):
    results = []

    for dep in batch:
        gdf_dep = gdf[gdf["Dep"] == dep]
        res_dep = nouveaux_batiments(gdf_dep, annee_min, rayon)
        results.append(res_dep)
        queue.put(1)
    return pd.concat(results, ignore_index=True)



def nouveaux_batiments(gdf, annee_min=2014, rayon=10):
    """
    Retourne un GeoDataFrame avec les bâtiments nouveaux à partir de annee_min
    en comparant ID et géométrie cumulée, par département.
    """
    gdf = gdf.copy()
    gdf['aire'] = gdf.geometry.area
    gdf = gdf.sort_values('Annee')
    annees = sorted(gdf['Annee'].unique())

    resultats = []

    nb_nouveaux = 0

    for dep in sorted(gdf['Dep'].unique()):
        gdf_dep = gdf[gdf['Dep'] == dep].copy()
        gdf_cumul = gdf_dep[gdf_dep['Annee'] < annee_min].copy()
        if not gdf_cumul.empty:
            sindex_cumul = gdf_cumul.sindex

        for annee in annees:
            if annee < annee_min:
                continue
            
            gdf_annee = gdf_dep[gdf_dep['Annee'] == annee].copy()
            nouveaux_idx = []
            nb_total = len(gdf_annee)
            

            for i, (idx, bat) in enumerate(gdf_annee.iterrows(), 1):
                #print(f"\rTraitement du dep {dep}, année {annee} ; jusqu'ici {nb_nouveaux} nouveaux bâtiments detectés", end="", flush=True)
                # Vérification ID
                if bat['ID'] in gdf_cumul['ID'].values:
                    continue

                # Vérification position
                if not gdf_cumul.empty:
                    candidates = list(sindex_cumul.intersection(bat.geometry.buffer(rayon).bounds))
                    possible_matches = gdf_cumul.iloc[candidates]
                    if any(possible_matches.distance(bat.geometry) <= rayon):
                        continue

                # Nouveau bâtiment
                nb_nouveaux += 1
                nouveaux_idx.append(idx)

            gdf_annee_nouveaux = gdf_annee.loc[nouveaux_idx].copy()
            gdf_annee_nouveaux['Apparition_BDTopo'] = annee
            resultats.append(gdf_annee_nouveaux)

            # Mettre à jour cumul pour l'année suivante
            gdf_cumul = pd.concat([gdf_cumul, gdf_annee_nouveaux], ignore_index=True)
            if not gdf_cumul.empty:
                sindex_cumul = gdf_cumul.sindex

    if resultats:
        return gpd.GeoDataFrame(pd.concat(resultats, ignore_index=True), crs=gdf.crs)
    else:
        return gpd.GeoDataFrame(columns=gdf.columns.tolist() + ['Apparition_BDTopo'], crs=gdf.crs)

######################
# POUR CREER UN STOCK
####################


def stock_build(gdf, annee_min=2008, annee_max=2013, rayon=10):
    """
    Construit un GeoDataFrame cumulatif de bâtiments uniques par géométrie
    de 2008 à 2013 (inclus) avec un buffer pour éviter les doublons.
    """
    gdf = gdf.copy()
    gdf = gdf.sort_values('Apparition_BDTopo')
    annees = list(range(annee_min, annee_max + 1))
    
    stock = []  # liste pour stocker les résultats

    for dep in sorted(gdf['Dep'].unique()):
        print(f"\rTraitement du dep {dep}", flush=True)
        gdf_dep = gdf[gdf['Dep'] == dep].copy()
        cumul_dep = gdf_dep[gdf_dep['Apparition_BDTopo'] < annee_min].copy()
        if not cumul_dep.empty:
            sindex_cumul = cumul_dep.sindex
        
        for annee in annees:
            gdf_annee = gdf_dep[gdf_dep['Apparition_BDTopo'] == annee].copy()
            nouveaux_idx = []

            for idx, bat in gdf_annee.iterrows():
                # Vérification ID
                if bat['ID'] in cumul_dep['ID'].values:
                    continue

                # Vérification position
                if not cumul_dep.empty:
                    candidates = list(sindex_cumul.intersection(bat.geometry.buffer(rayon).bounds))
                    if candidates:
                        possible_matches = cumul_dep.iloc[candidates]
                        if any(possible_matches.distance(bat.geometry) <= rayon):
                            continue

                # Nouveau bâtiment
                nouveaux_idx.append(idx)

            # Ajouter les nouveaux bâtiments de l'année au cumul
            gdf_nouveaux = gdf_annee.loc[nouveaux_idx].copy()
            stock.append(gdf_nouveaux)
            cumul_dep = pd.concat([cumul_dep, gdf_nouveaux], ignore_index=True)
            if not cumul_dep.empty:
                sindex_cumul = cumul_dep.sindex

    if stock:
        stock_df = gpd.GeoDataFrame(pd.concat(stock, ignore_index=True), crs=gdf.crs)
    else:
        stock_df = gpd.GeoDataFrame(columns=gdf.columns.tolist(), crs=gdf.crs)
    
    # Ajouter colonne Annee_REF = 2013 et supprimer Apparition_BDTopo
    stock_df['Annee_REF'] = 2013
    if 'Apparition_BDTopo' in stock_df.columns:
        stock_df.drop(columns=['Apparition_BDTopo'], inplace=True)
    
    return stock_df




from multiprocessing import Process, Queue, cpu_count
import geopandas as gpd
import pandas as pd

def worker(gdf, deps, queue, annee_min=2008, annee_max=2013, rayon=10):
    """
    Worker pour traiter un sous-ensemble de départements avec stock_build
    """
    gdf_sub = gdf[gdf['Dep'].isin(deps)]
    stock_sub = stock_build(gdf_sub, annee_min, annee_max, rayon)
    queue.put(stock_sub)  # renvoie le résultat dans la queue

def parallel_stock_build(gdf, annee_min=2008, annee_max=2013, rayon=10, n_cpu=None):
    """
    Parallélisation de stock_build par département
    """
    if n_cpu is None:
        n_cpu = max(1, cpu_count() - 1)

    deps = sorted(gdf['Dep'].unique())
    # Découpage des départements en n_cpu lots
    batches = [deps[i::n_cpu] for i in range(n_cpu)]

    queue = Queue()
    processes = []

    for batch in batches:
        p = Process(target=worker, args=(gdf, batch, queue, annee_min, annee_max, rayon))
        p.start()
        processes.append(p)

    # Récupérer les résultats
    results = []
    for _ in processes:
        results.append(queue.get())

    # Attendre que tous les processus terminent
    for p in processes:
        p.join()

    # Concaténer tous les résultats
    stock_df = gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs=gdf.crs)
    stock_df['Annee_REF'] = 2013
    if 'Apparition_BDTopo' in stock_df.columns:
        stock_df.drop(columns=['Apparition_BDTopo'], inplace=True)

    return stock_df
