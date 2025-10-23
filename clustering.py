from fonctions import load_gpkg, gdf_DBSCAN
import geopandas as gpd
import pandas as pd
import numpy as np

gdf=load_gpkg("BDTOPO/BDTOPO_BATI_merge_dep_81_99.gpkg")



gdf["Annee"].unique()
gdf["aire"] = gdf.geometry.area

centroids = gdf.geometry.centroid
# Conversion en coordonnées géographiques (WGS84)
centroids_wgs84 = gpd.GeoSeries(centroids, crs=2154).to_crs(epsg=4326)
gdf["lon"] = centroids_wgs84.x
gdf["lat"] = centroids_wgs84.y

gdf=gdf[gdf["Annee"].isin([2008,2014,2020,2025])]


#identification de sites industriels et logistiques
temp=gdf_DBSCAN(gdf,2008,eps=300,min_samples=2)
temp=temp[temp["cluster_id"]==-1]
isolés = temp[temp["cluster_id"] == -1].copy()
clusterisés = temp[temp["cluster_id"] != -1].copy()
clusterisés["centroid"] = clusterisés.geometry.centroid
clusters_fusionnes = clusterisés.groupby("cluster_id")["centroid"].apply(
    lambda centroids: Point(
        np.mean([p.x for p in centroids]),
        np.mean([p.y for p in centroids])
    )
).reset_index()
gdf_clusters_fusionnes = gpd.GeoDataFrame(
    clusters_fusionnes, 
    geometry="centroid", 
    crs=temp.crs
)
gdf_clusters_fusionnes = gdf_clusters_fusionnes.set_geometry("centroid")
temp = pd.concat([isolés, gdf_clusters_fusionnes], ignore_index=True)

#clusters 
gdf_DBSCAN(temp,2008,eps=1000,min_samples=3)


print(df.head())