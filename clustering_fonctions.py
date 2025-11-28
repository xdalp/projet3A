import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from multiprocessing import Pool, cpu_count

def dbscan_sequentiel_dep(gdf_dep, eps=500, min_samples=7):
    gdf_dep = gdf_dep.copy().sort_values("Annee_REF")
    dep_code = int(gdf_dep["DEP_CODE"].iloc[0])
    cluster_counter = dep_code * 100_000

    # On prépare une colonne cluster_id globale (pour les votes majoritaires)
    gdf_dep["cluster_id"] = -1

    for annee in sorted(gdf_dep["Annee_REF"].unique()):
        # Sous-ensemble cumulatif jusqu'à l'année courante
        gdf_cumul = gdf_dep[gdf_dep["Annee_REF"] <= annee].copy()

        # Extraction des coordonnées
        coords = np.array([
            [geom.x, geom.y] if geom.geom_type == "Point"
            else [geom.centroid.x, geom.centroid.y]
            for geom in gdf_cumul.geometry
        ])

        # DBSCAN global
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(coords)
        gdf_cumul["tmp_label"] = labels

        # Dictionnaire de correspondance tmp_label → cluster_id continu
        map_label_to_id = {}

        for lbl in sorted(gdf_cumul["tmp_label"].unique()):
            if lbl == -1:
                continue

            subset = gdf_cumul[gdf_cumul["tmp_label"] == lbl]
            old = subset[subset["Annee_REF"] < annee]

            if len(old) == 0:
                # Nouveau cluster
                cluster_counter += 1
                map_label_to_id[lbl] = cluster_counter
            else:
                # Vote majoritaire sur les anciens IDs
                maj = old["cluster_id"].loc[old["cluster_id"] > 0].mode()
                if len(maj) > 0:
                    map_label_to_id[lbl] = maj.iloc[0]
                else:
                    cluster_counter += 1
                    map_label_to_id[lbl] = cluster_counter

        # Application : conversion des labels
        for lbl, cid in map_label_to_id.items():
            idx = gdf_cumul[gdf_cumul["tmp_label"] == lbl].index
            gdf_dep.loc[idx, "cluster_id"] = cid

        # Créer la colonne spécifique à l'année
        colname = f"cluster_id_{annee}"
        gdf_dep[colname] = gdf_dep["cluster_id"]

    return gdf_dep


def run_dbscan_parallele(gdf, eps=500, min_samples=7, n_cpu=None):
    """
    DBSCAN parallèle par département
    """
    if n_cpu is None:
        n_cpu = max(1, cpu_count() - 1)

    deps = sorted(gdf['DEP_CODE'].unique())
    gdf_groups = [gdf[gdf['DEP_CODE'] == dep] for dep in deps]

    with Pool(n_cpu) as pool:
        results = pool.starmap(dbscan_sequentiel_dep, [(grp, eps, min_samples) for grp in gdf_groups])

    return gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs=gdf.crs)
