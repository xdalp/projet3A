import pandas as pd
from fonctions import list_files_onyxia
from fonctions import parallel_process

files=list_files_onyxia()
df=parallel_process(files)

gdf = process_file("BDTOPO/2017_74.7z")
pd.set_option('display.max_columns', None)
print(gdf.head())

