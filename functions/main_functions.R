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



# ------------------------------------------------------------------ #
#  SPLIT : une estimation par élection + facet_wrap                   #
# ------------------------------------------------------------------ #
rdd_split <- function(df, outcome_var, y_label = outcome_var,
                      kernel_choisi = "tri", elections = c(2014, 2020),
                      running_var = "delta_score_1", cutoff = 0,
                      cov_choisies = NULL, bw = 8, poly_fit = 1) {

  col_left  <- brewer.pal(11, "RdBu")[2]
  col_right <- brewer.pal(11, "RdBu")[9]

  results     <- list()
  df_pts_all  <- list()
  df_bins_all <- list()
  df_fit_all  <- list()

  for (elec in elections) {

    df_rdd   <- df %>% filter(election == elec)
    covs_mat <- NULL
    if (!is.null(cov_choisies) && cov_choisies != "aucun")
      covs_mat <- df_rdd[, cov_choisies, drop = FALSE]

    res <- rdrobust(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                    c = cutoff, covs = covs_mat, kernel = kernel_choisi,
                    h = bw, p = poly_fit)

    bw_left  <- res$bws[1, 1]
    bw_right <- res$bws[1, 2]

    rd_p <- rdplot(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                   c = cutoff, h = c(bw_left, bw_right), p = poly_fit, hide = TRUE)

    n_left  <- sum(df_rdd[[running_var]] <  cutoff & df_rdd[[running_var]] >= (cutoff - bw_left))
    n_right <- sum(df_rdd[[running_var]] >= cutoff & df_rdd[[running_var]] <= (cutoff + bw_right))

    # Ligne traitement
    row_treat <- data.frame(
      variable    = "Traitement",
      coefficient = res$Estimate[1, 1],
      std_error   = res$se[1, 1],
      p_value     = res$pv[1, 1]
    )

    # Lignes covariables
    rows_covs <- if (!is.null(cov_choisies) && cov_choisies != "aucun" && !is.null(res$beta_covs)) {
      data.frame(
        variable    = cov_choisies,
        coefficient = as.numeric(res$beta_covs),
        std_error   = NA_real_,
        p_value     = NA_real_
      )
    } else NULL

    # Ligne spec
    row_meta <- data.frame(
      variable    = paste0("Spec. BW: [–", round(bw_left, 2), ", +", round(bw_right, 2),
                           "]  |  N: ", n_left, " / ", n_right),
      coefficient = NA_real_,
      std_error   = NA_real_,
      p_value     = NA_real_
    )

    results[[as.character(elec)]] <- list(
      table = bind_rows(row_treat, rows_covs, row_meta),
      bw_left = bw_left, bw_right = bw_right,
      n_left = n_left, n_right = n_right
    )

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

  # ---- Construction de la table avec surcolonnes ----
  tables_by_elec <- lapply(results, function(r) r$table)
  
  # Récupère toutes les variables possibles (union des lignes)
  all_vars <- unique(unlist(lapply(tables_by_elec, function(t) t$variable)))
  
  # Jointure large : une colonne coef/se/pv par élection
  wide_table <- data.frame(variable = all_vars)
  
  for (elec in as.character(elections)) {
    t <- tables_by_elec[[elec]]
    colnames(t) <- c("variable",
                     paste0("coef_",  elec),
                     paste0("se_",    elec),
                     paste0("pval_",  elec))
    wide_table <- left_join(wide_table, t, by = "variable")
  }

  # kable avec surcolonnes via kableExtra
  col_names_display <- c("", rep(c("Coef.", "SE", "p-val"), length(elections)))
  
  header <- c(" " = 1)
  for (elec in as.character(elections))
    header[as.character(elec)] <- 3

  tbl <- kable(wide_table, digits = 3, col.names = col_names_display,
               caption = paste("RDD results for", y_label)) %>%
    add_header_above(header)

  # ---- Graphique (inchangé) ----
  df_pts  <- bind_rows(df_pts_all)
  df_bins <- bind_rows(df_bins_all)
  df_fit  <- bind_rows(df_fit_all)

  facet_labels <- sapply(as.character(elections), function(elec) {
    r <- results[[elec]]
    paste0(elec, "  |  BW: [–", round(r$bw_left, 2), ", +", round(r$bw_right, 2), "]")
  })

  x_lim <- if (is.null(bw)) {
    max_bw <- max(sapply(results, function(r) max(r$bw_left, r$bw_right)))
    c(-max(8, max_bw), max(8, max_bw))
  } else {
    c(-max(8, bw), max(8, bw))
  }

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

  return(list(table = tbl, plot = p))
}

# ------------------------------------------------------------------ #
#  AGGREGATED : estimation poolée avec dummies d'élection             #
# ------------------------------------------------------------------ #
rdd_aggregated <- function(df, outcome_var, y_label = outcome_var,
                           kernel_choisi = "tri", elections = c(2014, 2020),
                           running_var = "delta_score_1", cutoff = 0,
                           cov_choisies = NULL, bw = 8, poly_fit = 1) {

  col_left  <- brewer.pal(11, "RdBu")[2]
  col_right <- brewer.pal(11, "RdBu")[9]

  df_rdd <- df %>% filter(election %in% elections)

  election_dummies <- model.matrix(~ factor(election), data = df_rdd)[, -1, drop = FALSE]
  colnames(election_dummies) <- paste0("election_", elections[-1])

  covs_mat <- election_dummies
  if (!is.null(cov_choisies) && cov_choisies != "aucun")
    covs_mat <- cbind(df_rdd[, cov_choisies, drop = FALSE], election_dummies)

  res <- rdrobust(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                  c = cutoff, covs = covs_mat, kernel = kernel_choisi,
                  h = bw, p = poly_fit)

  bw_left  <- res$bws[1, 1]
  bw_right <- res$bws[1, 2]

  rd_p <- rdplot(y = df_rdd[[outcome_var]], x = df_rdd[[running_var]],
                 c = cutoff, h = c(bw_left, bw_right), p = poly_fit, hide = TRUE)

  n_left  <- sum(df_rdd[[running_var]] <  cutoff & df_rdd[[running_var]] >= (cutoff - bw_left))
  n_right <- sum(df_rdd[[running_var]] >= cutoff & df_rdd[[running_var]] <= (cutoff + bw_right))

  # ---- Construction de la table avec une ligne par variable ----
  
  # Ligne traitement
  row_treat <- data.frame(
    variable  = "Traitement",
    coefficient = res$Estimate[1, 1],
    std_error   = res$se[1, 1],
    p_value     = res$pv[1, 1]
  )

  # Lignes covariables (dummies élection + covariables supplémentaires)
  # rdrobust stocke les coefs covariables dans res$beta_covs
  cov_names <- colnames(covs_mat)
  
  rows_covs <- if (!is.null(res$beta_covs)) {
    data.frame(
      variable    = cov_names,
      coefficient = as.numeric(res$beta_covs),
      std_error   = NA_real_,   # rdrobust ne fournit pas les SE des covariables
      p_value     = NA_real_
    )
  } else {
    NULL
  }

  # Ligne métadonnées (BW, N) — une seule ligne fusionnée en bas
  row_meta <- data.frame(
    variable    = paste0("Spec. : BW: [–", round(bw_left, 2), ", +", round(bw_right, 2),
                         "]  |  N: ", n_left, " / ", n_right),
    coefficient = NA_real_,
    std_error   = NA_real_,
    p_value     = NA_real_
  )

  result_table <- bind_rows(row_treat, rows_covs, row_meta)

  # ---- Graphique (inchangé) ----
  df_pts <- df_rdd %>%
    select(x = all_of(running_var), y = all_of(outcome_var)) %>%
    filter(!is.na(x), !is.na(y)) %>%
    mutate(side = if_else(x < cutoff, "Gauche", "Droite"))

  df_bins <- rd_p$vars_bins %>%
    mutate(side = if_else(rdplot_mean_x < cutoff, "Gauche", "Droite"))

  df_fit <- rd_p$vars_poly %>%
    mutate(side = if_else(rdplot_x < cutoff, "Gauche", "Droite"))

  x_lim <- c(-max(8, bw), max(8, bw))
  
  subtitle_text <- paste0(
    "2014–2020 & 2020–2025",
    "  |  BW: [–", round(bw_left, 2), ", +", round(bw_right, 2), "]"
  )

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
    scale_color_manual(values = c("Gauche" = col_left, "Droite" = col_right),
                       guide = "none") +
    coord_cartesian(xlim = x_lim) +
    theme_minimal()+
    labs(x = "Écart au score", y = y_label, subtitle = subtitle_text)


  return(list(
    table = kable(result_table, digits = 3,
                  caption = paste("RDD results for", y_label)),
    plot  = p
  ))
}


# ------------------------------------------------------------------ #
#  WRAPPER : route vers la bonne fonction selon option                #
# ------------------------------------------------------------------ #
rdd_table_plot <- function(df, outcome_var, y_label = outcome_var,
                           kernel_choisi = "tri", elections = c(2014, 2020),
                           running_var = "delta_score_1", cutoff = 0,
                           cov_choisies = NULL, bw = 8, poly_fit = 1,
                           option = "aggregated") {

  args <- list(df = df, outcome_var = outcome_var, y_label = y_label,
               kernel_choisi = kernel_choisi, elections = elections,
               running_var = running_var, cutoff = cutoff,
               cov_choisies = cov_choisies, bw = bw, poly_fit = poly_fit)

  switch(option,
    split      = do.call(rdd_split,      args),
    aggregated = do.call(rdd_aggregated, args),
    stop('`option` doit être "split" ou "aggregated".')
  )
}