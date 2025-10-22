import pandas as pd
from fonctions import list_files_onyxia, upload_to_onyxia,parallel_process,check_corrompu
import os 

#files=list_files_onyxia()
#files = [
#    f for f in files
#    if len(f.split("_")) > 1 and f.split("_")[1].split(".")[0].isdigit() and int(f.split("_")[1].split(".")[0]) < 2
#]

#TEST EXISTENCE FICHIERS CORROMPUS ()
#if __name__ == "__main__":
    # Vérifie leur intégrité
#    corrompus = check_corrompu(files, max_workers=10, bucket="mgarbe")
#    print("Fichiers corrompus :", corrompus)

#print(files)
#df=parallel_process(files)
#output_file = "BDTOPO_BATI_merge.gpkg"
#df.to_file(output_file, driver="GPKG")
#upload_to_onyxia(output_file, bucket="mgarbe", remote_path=f"BDTOPO/{output_file}")
#if os.path.exists(output_file):
#    os.remove(output_file)
#    print(f"Fichier local supprimé : {output_file}")

files = list_files_onyxia()
# On ne garde que les fichiers des départements < 2 (exemple de filtre)
files = [
    f for f in files
    if len(f.split("_")) > 1 and f.split("_")[1].split(".")[0].isdigit()
]
files = sorted(files, key=lambda x: int(x.split("_")[1].split(".")[0]))

print(files)

# Définition des tranches de départements
ranges = [
    range(1, 21),   # 1-20
    range(21, 41),  # 21-40
    range(41, 61),  # 41-60
    range(61, 81),  # 61-80
    range(81, 100)  # 81 et plus
]

bucket = "mgarbe"

for i, dep_range in enumerate(ranges, start=1):
    # Filtrer les fichiers correspondant à la tranche de départements
    files_range = [
        f for f in files
        if int(f.split("_")[1].split(".")[0]) in dep_range
    ]

    if not files_range:
        print(f"Aucun fichier pour la tranche {dep_range.start}-{dep_range.stop-1}")
        continue

    print(f"Fusion de la tranche {dep_range.start}-{dep_range.stop-1} ({len(files_range)} fichiers)...")
    df = parallel_process(files_range)

    # Nom du fichier GeoPackage pour cette tranche
    output_file = f"BDTOPO_BATI_merge_dep_{dep_range.start}_{dep_range.stop-1}.gpkg"
    df.to_file(output_file, driver="GPKG")

    # Upload sur Onyxia
    remote_path = f"BDTOPO/{output_file}"
    upload_to_onyxia(output_file, bucket=bucket, remote_path=remote_path)
    print(f"Fichier envoyé : {remote_path}")

    # Suppression du fichier local
    if os.path.exists(output_file):
        os.remove(output_file)
        print(f"Fichier local supprimé : {output_file}")
