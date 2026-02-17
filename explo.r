rdd_indic_permis <- rdd_report(gdf_RDD_seuil,"dummy_permis", kernel = "uni") 
rdd_indic_permis

rdd_indic_surface <- rdd_report(gdf_RDD_seuil,"dummy_surface_creee", kernel = "uni")
rdd_indic_surface
head(gdf_RDD_seuil['dummy_surface_creee','dummy_permis'])

hist_variable(gdf_RDD, delta_score_1)
dim(gdf_RDD)

outlier <- gdf_RDD[gdf_RDD$surface_creee > 300000,]
summary(gdf_RDD)
outlier$surface_creee
