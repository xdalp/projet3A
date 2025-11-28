import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from multiprocessing import Pool, cpu_count

def dbscan_sequentiel_dep(gdf_dep, eps=50, min_samples=3, start_year=2014):
    """
    DBSCAN séquentiel pour un seul département.
    - gdf_dep : GeoDataFrame avec 'geometry', 'Annee_REF'
    - eps : rayon DBSCAN en mètres
    - min_samples : min points pour former un cluster
    """
    gdf_dep = gdf_dep.copy()
    gdf_dep = gdf_dep.sort_values('Annee_REF')
    gdf_dep['cluster_id'] = -1
    gdf_dep['cluster_ann'] = pd.NA
    cluster_counter = gdf_dep['DEP_CODE'].iloc[0] * 100_000  # id unique par département

    # Stock cumulatif de bâtiments déjà clusterisés
    gdf_cumul = gdf_dep[gdf_dep['Annee_REF'] < start_year].copy()
    sindex_cumul = gdf_cumul.sindex if not gdf_cumul.empty else None

    for annee in sorted(gdf_dep['Annee_REF'].unique()):
        if annee < start_year:
            continue

        gdf_new = gdf_dep[(gdf_dep['Annee_REF'] == annee) & (gdf_dep['cluster_id'] == -1)].copy()
        if gdf_new.empty:
            continue

        # Filtrer les points trop proches des anciens bâtiments
        if sindex_cumul is not None and not gdf_cumul.empty:
            indices_to_keep = []
            for idx, geom in gdf_new.geometry.items():
                possible = list(sindex_cumul.intersection(geom.bounds))
                if possible:
                    if (gdf_cumul.iloc[possible].geometry.distance(geom) <= eps).any():
                        continue
                indices_to_keep.append(idx)
            gdf_new = gdf_new.loc[indices_to_keep]
            if gdf_new.empty:
                continue

        coords = np.array([[geom.x, geom.y] if geom.geom_type=='Point' else [geom.centroid.x, geom.centroid.y]
                           for geom in gdf_new.geometry])

        # DBSCAN sur les nouveaux bâtiments filtrés
        db = DBSCAN(eps=eps, min_samples=min_samples)
        labels = db.fit_predict(coords)

        for i, idx in enumerate(gdf_new.index):
            if labels[i] != -1:
                gdf_dep.at[idx, 'cluster_id'] = cluster_counter + labels[i] + 1
                gdf_dep.at[idx, 'cluster_ann'] = annee

        cluster_counter += labels.max() + 2 if labels.max() >= 0 else 0

        # Mettre à jour le cumulatif
        gdf_cumul = pd.concat([gdf_cumul, gdf_dep.loc[gdf_dep['cluster_ann'] == annee]], ignore_index=True)
        sindex_cumul = gdf_cumul.sindex

    return gdf_dep


def run_dbscan_parallele(gdf, eps=50, min_samples=3, start_year=2014, n_cpu=None):
    """
    DBSCAN parallèle par département
    """
    if n_cpu is None:
        n_cpu = max(1, cpu_count() - 1)

    deps = sorted(gdf['DEP_CODE'].unique())
    gdf_groups = [gdf[gdf['DEP_CODE'] == dep] for dep in deps]

    with Pool(n_cpu) as pool:
        results = pool.starmap(dbscan_sequentiel_dep, [(grp, eps, min_samples, start_year) for grp in gdf_groups])

    return gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs=gdf.crs)
