import pandas as pd
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt
import seaborn as sns
import requests

def compute_rdd(df, outcome_var, running_var='delta_score_1', cutoff=0):
    """
    Calcule un RDD linéaire pour chaque élection.
    """
    results = {}
    for e in df['election'].unique():
        df_e = df[df['election'] == e].copy()
        df_e['treatment'] = (df_e[running_var] >= cutoff).astype(int)
        
        # OLS linéaire RDD
        formula = f"{outcome_var} ~ treatment + {running_var}"
        model = smf.ols(formula, data=df_e).fit()
        
        results[e] = model.summary()
        
    return results


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



