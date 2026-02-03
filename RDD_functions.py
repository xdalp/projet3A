import pandas as pd
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import rdrobust

def compute_rdd(df, outcome_var, running_var='delta_score_1', cutoff=0, election = "2014_muni"):

# df,annee, type_kernel = "uni", bandwith_value = None):
# Sharp RDD
    df_rdd = df[df['election'] == election]

    res = rdrobust.rdrobust(
        y=df_rdd[outcome_var],
        x=df_rdd[running_var],
        #kernel = type_kernel,
        c = cutoff
        #,h = bandwith_value
    )
        
    return res


def plot_rdd(df, outcome_var, running_var='delta_score_1', cutoff=0):
    """
    Produit un graphique RDD gauche/droite pour chaque élection.
    """
    elections = df['election'].unique()
    
    for e in elections:
        df_e = df[df['election'] == e]
        
        plt.figure(figsize=(8,5))
        sns.scatterplot(x=running_var, y=outcome_var, data=df_e, alpha=0.5)
        sns.regplot(x=running_var, y=outcome_var, data=df_e[df_e[running_var] < cutoff],
                    scatter=False, label='Left fit', color='red')
        sns.regplot(x=running_var, y=outcome_var, data=df_e[df_e[running_var] >= cutoff],
                    scatter=False, label='Right fit', color='blue')
        
        plt.axvline(cutoff, color='black', linestyle='--')
        plt.title(f'RDD - Election {e} ({outcome_var})')
        plt.xlabel(running_var)
        plt.ylabel(outcome_var)
        plt.legend()
        plt.show()




def plot_rdd_package(df, outcome_var, running_var='delta_score_1', election = "2014_muni"):
    df_rdd = df[df['election'] == election]
    figure_rdd = rdrobust.rdplot(y=df_rdd[outcome_var],
                    x=df_rdd[running_var],
                    ci=95,
                    y_label= outcome_var,
                    x_label=running_var)

    return(figure_rdd)
