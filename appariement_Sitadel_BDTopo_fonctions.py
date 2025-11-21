import geopandas as gpd
import pandas as pd


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
                print(f"\rTraitement du dep {dep}, année {annee} ; jusqu'ici {nb_nouveaux} nouveaux bâtiments detectés", end="", flush=True)
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
