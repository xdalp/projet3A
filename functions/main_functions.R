library(dplyr)
library(ggplot2)
library(rdrobust)
library(aws.s3)
library(readr)
library(dplyr)
library(rdrobust)
library(sf)
library(RColorBrewer)

get_s3_csv <- function(bucket,file_key,delim_csv = ";") {
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
    delim = delim_csv, # Spécifie le séparateur correct
    object = file_key,
    bucket = bucket,
    opts = list("region" = "")
  )
  return(df)
}

get_s3_gpkg <- function(bucket, file_key) {
  
  Sys.setenv(
    AWS_ACCESS_KEY_ID     = Sys.getenv("AWS_ACCESS_KEY_ID"),
    AWS_SECRET_ACCESS_KEY = Sys.getenv("AWS_SECRET_ACCESS_KEY"),
    AWS_SESSION_TOKEN     = Sys.getenv("AWS_SESSION_TOKEN"),
    AWS_DEFAULT_REGION    = "us-east-1",
    AWS_S3_ENDPOINT       = "minio.lab.sspcloud.fr"
  )
  
  df <- aws.s3::s3read_using(
    FUN = sf::st_read,
    object = file_key,
    bucket = bucket,
    quiet = TRUE,
    opts = list(region = "")
  )
  
  return(df)
}

compute_rdd <- function(df,
                        outcome_var,
                        kernel_choisi = "uni",
                        elections = c("2014_muni", "2020_muni"),
                        running_var = "delta_score_1",
                        cutoff = 0,
                        cov_choisies = NULL) {
  
  # Boucle sur toutes les élections
  results <- lapply(elections, function(elec) {
    
    # Filtrage sur l'élection
    df_rdd <- df %>% filter(election == elec)
    
    # Covariables
    covs_mat <- NULL
    if (!is.null(cov_choisies) && cov_choisies != "aucun") {
      covs_mat <- df_rdd[, cov_choisies, drop = FALSE]
    }
    
    # Estimation RDD
    res <- rdrobust(
      y = df_rdd[[outcome_var]],
      x = df_rdd[[running_var]],
      c = cutoff,
      covs = covs_mat,
      kernel = kernel_choisi
    )
    
    # Table pour cette élection
    data.frame(
      outcome = outcome_var,
      election = elec,
      coefficient = res$Estimate[1, 1],
      std_error = res$se[1, 1],
      p_value = res$pv[1, 1],
      row.names = NULL
    )
    
  })
  
  # Empiler les résultats
  do.call(rbind, results)
}


plot_rdd <- function(df, outcome_var, running_var = "delta_score_1", cutoff = 0) {
  p <- ggplot(df, aes_string(x = running_var, y = outcome_var)) +
    geom_point(alpha = 0.5) +
    geom_smooth(
      data = df %>% filter(.data[[running_var]] < cutoff),
      method = "lm",
      se = TRUE,
      color = brewer.pal(11, "RdBu")[2]
    ) +
    geom_smooth(
      data = df %>% filter(.data[[running_var]] >= cutoff),
      method = "lm",
      se = TRUE,
      color = brewer.pal(11, "RdBu")[9]
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

plot_rdd_kernel <- function(df,
                     outcome_var,
                     kernel = c("tri", "uni")) {
  
  kernel <- match.arg(kernel)
  df <- df %>%
    mutate(x = delta_score_1)
  
  max_abs_x <- max(abs(df$x), na.rm = TRUE)
  
  kernel_weights <- function(x) {
    if (kernel == "tri") {
      1 - abs(x) / max_abs_x
    } else {
      rep(1, length(x))
    }
  }
  
  df <- df %>%
    mutate(w = kernel_weights(x))
  
  fit_left <- lm(
    as.formula(paste(outcome_var, "~ x")),
    data = df %>% filter(x < 0),
    weights = w
  )
  
  fit_right <- lm(
    as.formula(paste(outcome_var, "~ x")),
    data = df %>% filter(x >= 0),
    weights = w
  )
  
  grid_left <- data.frame(
    x = seq(min(df$x), 0, length.out = 200)
  )
  
  grid_right <- data.frame(
    x = seq(0, max(df$x), length.out = 200)
  )
  
  grid_left <- cbind(
    grid_left,
    predict(fit_left, grid_left, interval = "confidence")
  )
  
  grid_right <- cbind(
    grid_right,
    predict(fit_right, grid_right, interval = "confidence")
  )
  
  ggplot(df, aes(x = x, y = .data[[outcome_var]])) +
    geom_point(alpha = 0.4) +
    
    # IC gauche (gris)
    geom_ribbon(
      data = grid_left,
      aes(x = x, ymin = lwr, ymax = upr),
      inherit.aes = FALSE,
      fill = "grey70",
      alpha = 0.4
    ) +
    
    # IC droit (gris)
    geom_ribbon(
      data = grid_right,
      aes(x = x, ymin = lwr, ymax = upr),
      inherit.aes = FALSE,
      fill = "grey70",
      alpha = 0.4
    ) +
    
    # Régression gauche (rouge)
    geom_line(
      data = grid_left,
      aes(x = x, y = fit),
      inherit.aes = FALSE,
      color = brewer.pal(11, "RdBu")[2],
      linewidth = 1
    ) +
    
    # Régression droite (bleu)
    geom_line(
      data = grid_right,
      aes(x = x, y = fit),
      inherit.aes = FALSE,
      color = brewer.pal(11, "RdBu")[9],
      linewidth = 1
    ) +
    
    geom_vline(xintercept = 0, linetype = "dashed") +
    
    labs(
      x = "Écart de score",
      y = "",
      title = paste("RDD – kernel", kernel)
    ) +
    
    facet_wrap(
      ~ election,
      labeller = as_labeller(
        c("2014_muni" = "2014", "2020_muni" = "2020")
      )
    ) +
    
    theme_minimal()
}




get_commune_contour <- function(code_insee) {
  url <- paste0("https://geo.api.gouv.fr/communes/", code_insee,
                "?format=geojson&geometry=centre")
  st_read(url, quiet = TRUE)
}