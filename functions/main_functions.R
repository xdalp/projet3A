library(dplyr)
library(ggplot2)
library(rdrobust)
library(aws.s3)
library(readr)

get_s3_csv <- function(bucket,file_key) {
  Sys.setenv(
    "AWS_ACCESS_KEY_ID"     = Sys.getenv("AWS_ACCESS_KEY_ID"),
    "AWS_SECRET_ACCESS_KEY" = Sys.getenv("AWS_SECRET_ACCESS_KEY"),
    "AWS_SESSION_TOKEN"     = Sys.getenv("AWS_SESSION_TOKEN"),
    "AWS_DEFAULT_REGION" = "us-east-1",
    "AWS_S3_ENDPOINT"= "minio.lab.sspcloud.fr"
  )
  
  # Lire le fichier CSV depuis S3
  df <- s3read_using(
    #FUN = readr::read_csv, # Fonction pour lire un CSV avec séparateur virgule
    FUN = readr::read_delim, # Fonction pour choisir le séparateur du csv
    delim = ";", # Spécifie le séparateur correct
    object = file_key,
    bucket = bucket,
    opts = list("region" = "")
  )
  return(df)
}




compute_rdd <- function(df,
                        outcome_var,
                        kernel_choisi = "uni",
                        election_choisie,
                        running_var = "delta_score_1",
                        cutoff = 0,
                        cov_choisies = NULL) {
  # Filtrage sur l'élection choisie
  df_rdd <- df %>% filter(election == election_choisie)

  covs_mat <- NULL
  if (!is.null(cov_choisies) && cov_choisies != "aucun") {
    covs_mat <- df_rdd[, cov_choisies, drop = FALSE]
  }

  # Appel à rdrobust
  res <- rdrobust(y = df_rdd[[outcome_var]],
                  x = df_rdd[[running_var]],
                  c = cutoff,
                  covs = covs_mat,
                  kernel = kernel_choisi)

  return(res)
  }



plot_rdd <- function(df, outcome_var, running_var = "delta_score_1", cutoff = 0) {
  p <- ggplot(df, aes_string(x = running_var, y = outcome_var)) +
    geom_point(alpha = 0.5) +
    geom_smooth(
      data = df %>% filter(.data[[running_var]] < cutoff),
      method = "lm",
      se = TRUE,
      color = "red"
    ) +
    geom_smooth(
      data = df %>% filter(.data[[running_var]] >= cutoff),
      method = "lm",
      se = TRUE,
      color = "blue"
    ) +
    geom_vline(xintercept = cutoff, linetype = "dashed") +
    labs(
      x = "Ecart de score",
      y=""
    ) +
    facet_wrap(~election, labeller = as_labeller(c("2014_muni"="2014","2020_muni"="2020"))) +
    theme_minimal()
  return(p)
}