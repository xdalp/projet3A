import pandas as pd
from fonctions import load_shapefile

gdf = load_shapefile("BDTOPO/2017_74.7z")
print(gdf["NATURE"].unique())
print(gdf["USAGE1"].unique())
pd.set_option('display.max_columns', None)
print(gdf.head())

