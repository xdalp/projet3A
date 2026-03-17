import pandas as pd
import unicodedata

#creation d'une fonction pour détecter là où débute vraiment le fichier
def detecter_ligne_header(fichier, mot_cle="Critère d'export", limite=15):
    preview = pd.read_excel(fichier, header=None, nrows=limite)

    for idx, row in preview.iterrows():
        if mot_cle in row.astype(str).values:
            return idx
    return 0



def simplifier_prenom(text):
    if pd.isna(text):
        return None   # ou "" ou text
    # Normalise en forme NFD (décompose les accents)
    text_normalized = unicodedata.normalize('NFD', text)
    # Garde seulement les caractères ASCII (supprime les accents)
    text_ascii = text_normalized.encode('ascii', 'ignore').decode('utf-8')
    text_clean = text_ascii.replace('-', ' ')
    return text_clean