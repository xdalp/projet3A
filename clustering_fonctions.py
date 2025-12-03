import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from multiprocessing import Pool, cpu_count
from shapely.geometry import Point

import numpy as np
import pandas as pd
from sklearn.neighbors import KDTree, sort_graph_by_row_values
from scipy.sparse import lil_matrix

def calc_distance_matrix_sparse(gdf_dep, radius_search=2000):
    """
    Calcule la matrice sparse des distances bord-à-bord pour un département.
    Ne considère que les bâtiments dans un rayon de radius_search autour du centroïde.
    """
    n = len(gdf_dep)
    
    # Coordonnées des centroïdes
    coords = np.array([geom.centroid.coords[0] if geom.geom_type != 'Point' else geom.coords[0]
                       for geom in gdf_dep.geometry])
    
    # Rayon de chaque bâtiment (cercles)
    radii = np.sqrt(np.where(gdf_dep['SURF_CREEE'].notna(),
                             gdf_dep['SURF_CREEE'],
                             gdf_dep.geometry.area) / np.pi)
    
    # Construire KDTree
    tree = KDTree(coords)
    
    # Matrice sparse vide
    D = lil_matrix((n, n), dtype=np.float32)
    
    # Calcul distances bord-à-bord uniquement pour voisins proches
    for i, (xi, yi, ri) in enumerate(zip(coords[:,0], coords[:,1], radii)):
        idx_neighbors = tree.query_radius([[xi, yi]], r=radius_search)[0]
        for j in idx_neighbors:
            if j <= i:
                continue  # matrice symétrique, on remplit seulement D[i,j] pour j>i
            xj, yj, rj = coords[j,0], coords[j,1], radii[j]
            d = max(0.0, np.hypot(xi - xj, yi - yj) - (ri + rj))
            D[i,j] = d
            D[j,i] = d  # symétrique
    
    D_csr = sort_graph_by_row_values(D.tocsr(), warn_when_not_sorted=False)

    return D_csr # convertir en format CSR pour sklearn DBSCAN


def dbscan_sequentiel_dep(gdf_dep, eps=500, min_samples=7):
    gdf_dep = gdf_dep.copy().sort_values("Annee_REF")
    dep_code = int(gdf_dep["DEP_CODE"].iloc[0])
    cluster_counter = dep_code * 100_000

    # Colonne cluster_id globale
    gdf_dep["cluster_id"] = -1

    years = sorted(gdf_dep["Annee_REF"].unique())

    for annee in years:
        # Données cumulées
        gdf_cumul = gdf_dep[gdf_dep["Annee_REF"] <= annee].copy()

        # Coordonnées (centroïde si polygone)
        coords = np.array([
            [geom.x, geom.y] if geom.geom_type == "Point"
            else [geom.centroid.x, geom.centroid.y]
            for geom in gdf_cumul.geometry
        ])

        # DBSCAN AVEC DISTANCES BORD A BORD
        D_sparse = calc_distance_matrix_sparse(gdf_cumul, radius_search=2000)
        db = DBSCAN(eps=eps, min_samples=min_samples, metric='precomputed')
        labels = db.fit_predict(D_sparse)
        #labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(coords) 
        gdf_cumul["tmp_label"] = labels

        map_label_to_id = {}

        for lbl in sorted(gdf_cumul["tmp_label"].unique()):
            if lbl == -1:
                continue  # bruit

            subset = gdf_cumul[gdf_cumul["tmp_label"] == lbl]
            old = subset[subset["Annee_REF"] < annee]
            old_ids = old["cluster_id"].loc[old["cluster_id"] > 0].unique()

            # --- 1. Points historiques existent : on force l'ID ---
            if len(old_ids) > 0:
                # Cluster majoritaire parmi les anciens points
                maj = old["cluster_id"].loc[old["cluster_id"] > 0].mode()
                cid_maj = maj.iloc[0] if len(maj) > 0 else old_ids[0]

                # Fusion rétroactive si plusieurs anciens cluster_id
                if len(old_ids) > 1:
                    for cid in old_ids:
                        if cid != cid_maj:
                            # Mettre à jour cluster_id global
                            gdf_dep.loc[gdf_dep["cluster_id"] == cid, "cluster_id"] = cid_maj
                            # Mettre à jour toutes les années déjà créées
                            for y in years:
                                col = f"cluster_id_{y}"
                                if col in gdf_dep.columns:
                                    gdf_dep.loc[gdf_dep[col] == cid, col] = cid_maj

                # Tous les points du tmp_label prennent cid_maj
                gdf_dep.loc[subset.index, "cluster_id"] = cid_maj

            # --- 2. Aucun historique : créer un nouveau cluster uniquement si assez de points ---
            else:
                if len(subset) >= min_samples:
                    cluster_counter += 1
                    cid_maj = cluster_counter
                    gdf_dep.loc[subset.index, "cluster_id"] = cid_maj
                else:
                    # Points isolés qui ne forment pas de cluster : rester -1
                    continue

            # Mémoriser le mapping tmp_label → cluster_id
            map_label_to_id[lbl] = gdf_dep.loc[subset.index[0], "cluster_id"]

        # Sauvegarde du cluster_id courant pour l'année
        colname = f"cluster_id_{annee}"
        gdf_dep[colname] = gdf_dep["cluster_id"]

    return gdf_dep

def dbscan_wrapper(args):
    gdf_dep, eps, min_samples = args
    return dbscan_sequentiel_dep(gdf_dep, eps, min_samples)



def run_dbscan_parallele(gdf, eps=500, min_samples=7, n_cpu=None):
    if n_cpu is None:
        n_cpu = max(1, cpu_count() - 1)

    deps = sorted(gdf['DEP_CODE'].unique())
    gdf_groups = [gdf[gdf['DEP_CODE'] == dep] for dep in deps]
    n_deps = len(deps)

    results = []
    count = 0
    with Pool(n_cpu) as pool:
        for res in pool.imap_unordered(dbscan_wrapper, [(grp, eps, min_samples) for grp in gdf_groups]):
            results.append(res)
            count += 1
            print(f"\rDépartements traités : {count}/{n_deps}", end="", flush=True)

    return gpd.GeoDataFrame(pd.concat(results, ignore_index=True), crs=gdf.crs)