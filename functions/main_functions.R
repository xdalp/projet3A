library(dplyr)
library(ggplot2)
library(rdrobust)
library(aws.s3)
library(readr)
library(dplyr)
library(rdrobust)
library(sf)
library(RColorBrewer)
library(grid)  

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



rdd_table_plot <- function(df, outcome_var, y_label = outcome_var,
                           kernel_choisi = "tri", elections = c(2014, 2020),
                           running_var = "delta_score_1", cutoff = 0,
                           cov_choisies = NULL, bw = 8,poly_fit=1) {

  results    <- list()
  df_pts_all <- list()
  df_bins_all <- list()
  df_fit_all  <- list()

  for (elec in elections) {

    df_rdd   <- df %>% filter(election == elec)
    covs_mat <- NULL
    if (!is.null(cov_choisies) && cov_choisies != "aucun")
      covs_mat <- df_rdd[, cov_choisies, drop = FALSE]

    res <- rdrobust(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                    c = cutoff, covs = covs_mat, kernel = kernel_choisi,
                    h = bw,p=poly_fit)

    bw_left  <- res$bws[1, 1]
    bw_right <- res$bws[1, 2]

    rd_p <- rdplot(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                   c = cutoff, h = c(bw_left, bw_right),p=poly_fit, hide = TRUE)

    n_left  <- sum(df_rdd[[running_var]] <  cutoff & df_rdd[[running_var]] >= (cutoff - bw_left))
    n_right <- sum(df_rdd[[running_var]] >= cutoff & df_rdd[[running_var]] <= (cutoff + bw_right))

    results[[as.character(elec)]] <- data.frame(
      outcome = outcome_var, election = elec,
      coefficient = res$Estimate[1, 1], std_error = res$se[1, 1],
      p_value = res$pv[1, 1], bw_left = bw_left, bw_right = bw_right,
      n_left = n_left, n_right = n_right
    )

    # Ajout colonne election pour le facet
    df_pts_all[[as.character(elec)]] <- df_rdd %>%
      select(x = all_of(running_var), y = all_of(outcome_var)) %>%
      filter(!is.na(x), !is.na(y)) %>%
      mutate(side = if_else(x < cutoff, "Gauche", "Droite"),
             election = as.character(elec))

    df_bins_all[[as.character(elec)]] <- rd_p$vars_bins %>%
      mutate(side = if_else(rdplot_mean_x < cutoff, "Gauche", "Droite"),
             election = as.character(elec))

    df_fit_all[[as.character(elec)]] <- rd_p$vars_poly %>%
      mutate(side = if_else(rdplot_x < cutoff, "Gauche", "Droite"),
             election = as.character(elec))
  }

  # Empilage de tous les dataframes
  df_pts  <- bind_rows(df_pts_all)
  df_bins <- bind_rows(df_bins_all)
  df_fit  <- bind_rows(df_fit_all)

  # Annotations BW par facet
  facet_labels <- do.call(rbind, results) %>%
    mutate(election = as.character(election),
           facet_label = paste0(election, "  |  BW: [–", round(bw_left, 2), ", +", round(bw_right, 2), "]")) %>%
    select(election, facet_label) %>%
    deframe()  # named vector election -> label

  x_lim <- if (is.null(bw)) {
    max_bw <- max(sapply(results, function(r) max(r$bw_left, r$bw_right)))
    c(-max(8, max_bw), max(8, max_bw))
  } else {
    c(-max(8, bw), max(8, bw))
  }

  col_left  <- brewer.pal(11, "RdBu")[2]
  col_right <- brewer.pal(11, "RdBu")[9]

  p <- ggplot() +
    geom_point(data = df_pts,
               aes(x = x, y = y, color = side),
               alpha = 0.15, size = 0.8, shape = 16) +
    geom_point(data = df_bins,
               aes(x = rdplot_mean_x, y = rdplot_mean_y, color = side),
               size = 2.2) +
    geom_line(data = df_fit,
              aes(x = rdplot_x, y = rdplot_y, color = side),
              linewidth = 1) +
    geom_vline(xintercept = cutoff, linetype = "dashed",
               color = "black", linewidth = 0.5) +
    facet_wrap(~ election, labeller = as_labeller(facet_labels)) +
    scale_color_manual(values = c("Gauche" = col_left, "Droite" = col_right),
                       guide = "none") +
    labs(x = "Écart au score", y = y_label) +
    coord_cartesian(xlim = x_lim) +
    theme_minimal()

  final_table <- do.call(rbind, results) %>%
    rename(`outcome` = outcome) %>%
    mutate(outcome = y_label)
  
  return(list(
    table = kable(final_table, digits = 3,
                  caption = paste("RDD results for", y_label)),
    plot  = p
  ))
}




get_commune_contour <- function(code_insee) {
  url <- paste0("https://geo.api.gouv.fr/communes/", code_insee,
                "?format=geojson&geometry=centre")
  
  tryCatch(
    sf::st_read(url, quiet = TRUE),
    error = function(e) {
      message("Impossible de récupérer le centre de la commune ", code_insee)
      return(NULL)
    }
  )
}