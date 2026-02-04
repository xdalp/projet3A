"""
Ce fichier contient les fonctions en R pour l'économétrie et la dataviz
"""
library(dplyr)
library(ggplot2)
library(rdrobust)

compute_rdd <- function(df,
                        outcome_var,
                        running_var = "delta_score_1",
                        cutoff = 0,
                        election = "2014_muni") {

  # Filtrage sur l'élection choisie
  df_rdd <- df %>%
            filter(election == election)

  # Appel à rdrobust
  res <- rdrobust(y = df_rdd[[outcome_var]],
                    x = df_rdd[[running_var]],
                    c = cutoff
                )

  return(res)
  }




plot_rdd <- function(df,
                     outcome_var,
                     e,
                     running_var = "delta_score_1",
                     cutoff = 0) {

  # Filtrage par élection
  df_e <- df %>%
            filter(election == e)

  ggplot(df_e, aes_string(x = running_var, y = outcome_var)) +
        geom_point(alpha = 0.5) +

    # Ajustement à gauche du cutoff
    geom_smooth(
      data = df_e %>% filter(.data[[running_var]] < cutoff),
      method = "lm",
      se = FALSE,
      color = "red"
    ) +
    # Ajustement à droite du cutoff
    geom_smooth(
      data = df_e %>% filter(.data[[running_var]] >= cutoff),
      method = "lm",
      se = FALSE,
      color = "blue"
    ) +

    # Ligne verticale au cutoff
    geom_vline(xintercept = cutoff, linetype = "dashed") +

    labs(
      title = paste0("RDD - Election ", e, " (", outcome_var, ")"),
      x = running_var,
      y = outcome_var
    ) +
    theme_minimal()
}


