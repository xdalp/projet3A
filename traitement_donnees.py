import pandas as pd
from fonctions import list_files_onyxia
from fonctions import parallel_process
from fonctions import check_corrompu


files=list_files_onyxia()
files = [
    f for f in files
    if len(f.split("_")) > 1 and f.split("_")[1].split(".")[0].isdigit() and int(f.split("_")[1].split(".")[0]) < 2
]

#TEST EXISTENCE FICHIERS CORROMPUS ()
#if __name__ == "__main__":
    # Vérifie leur intégrité
#    corrompus = check_corrompu(files, max_workers=10, bucket="mgarbe")
#    print("Fichiers corrompus :", corrompus)

#print(files)
df=parallel_process(files)


#print(df.head())
#gdf = process_file("BDTOPO/2017_74.7z")
#pd.set_option('display.max_columns', None)
#print(gdf.head())

