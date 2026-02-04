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




plot_rdd <- function(df_e, outcome_var,running_var = "delta_score_1",cutoff = 0) {
df_e <- df %>%
  ggplot(df_e, aes_string(x = running_var, y = outcome_var)) +
  geom_point(alpha = 0.5) +
  geom_smooth(
    data = df_e %>% filter(.data[[running_var]] < cutoff),
    method = "lm",
    se = FALSE,
    color = "red") + 
  geom_smooth(
      data = df_e %>% filter(.data[[running_var]] >= cutoff),
      method = "lm",
      se = FALSE,
      color = "blue"
    ) +
  geom_vline(xintercept = cutoff, linetype = "dashed") +
  labs(
      title = paste0("RDD - Election ", e, " (", outcome_var, ")"),
      x = running_var,
      y = outcome_var
    ) +
  facet_wrap(election)
  theme_minimal()
}