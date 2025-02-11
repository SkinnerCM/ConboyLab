
"""
------------------------------------------------------------------------------
 Author: Colin M. Skinner
 Date Created: 2024-08-02
 Last Modified: 2024-08-10
 Description: A collection of functions for analyzing the feature selection
              of methylation clocks. This script enables analysis of CpG site 
              feature importance, correlation, heteroscedasticity, and group 
              comparison statistics. The functions are designed for import into 
              a Jupyter Notebook or other interactive environment.

 Dependencies:  pandas, numpy, scipy, utils.data_processing (custom module)
 Usage: Import `feature_selection_analyses.py` into a Jupyter Notebook or other
        Python environment and call the desired functions for feature analysis.


 Notes: - The script provides multiple analysis functions, including:
        - `get_stats`: Computes regression statistics for CpG data.
        - `get_tvals`: Calculates t-values to assess feature significance.
        - `model_corrs`: Correlates model CpGs with reference data.
        - `normalized_importance`: Calculates normalized feature importances.
        - `het_r`: Measures noise correlation with age.
        - `u_test`: Performs Mann-Whitney U test for two sample groups.
        - No direct command-line execution is available; import and use functions as needed.
 ------------------------------------------------------------------------------
 """

import pandas as pd 
import numpy as np 
from scipy import stats
from utils.data_processing import prep_model


def get_stats(dataset, meta):
    """
    Compute regression statistics for each column in the dataset.

    This function performs linear regression for each column in the dataset
    against the age data provided in the meta DataFrame. It calculates the
    correlation coefficient and standard error for each regression.

    Parameters:
    dataset (pd.DataFrame): A DataFrame where each column contains CpG site data
                            for regression analysis.
    meta (pd.DataFrame): A DataFrame containing metadata with an 'age' column containing sample ages.

    Returns:
    tuple: A tuple containing two lists:
        - rs (list of float): The correlation coefficients (r-values) from the regression.
        - stderrs (list of float): The standard errors of the regression slopes.
    """
    rs = []
    stderrs = []

    for column in dataset:
        # Perform linear regression between age and the current column
        regression = stats.linregress(meta.age.astype(float), dataset[column].astype(float))
        slope, intercept, rvalue, pvalue, stderr = regression
        rs.append(rvalue)
        stderrs.append(stderr)
        
    return rs, stderrs

def get_tvals(weights, stderrs):
    """
    Calculate feature importances based on t-values.

    This function computes the t-values for each feature using the formula:
    t = weight / standard error. The t-values indicate the significance of each
    feature's weight.

    Parameters:
    weights (list of float): A list of feature weights.
    stderrs (list of float): A list of standard errors corresponding to each feature weight.

    Returns:
    list of float: A list of t-values for each feature.
    """
    tvals = []
    for i in range(len(weights)):
        tvals.append(weights[i] / stderrs[i])
        
    return tvals

def model_corrs(model, ref_data, meta):
    """
    Calculate the correlations and feature importances between a model and reference dataset.

    This function identifies the intersection of CpG sites between a reference dataset and a model dataset,
    computes the age-correlations and t-statistics for the CpGs in the model, and returns a DataFrame with
    the results. It also identifies any CpG sites present in the model but missing from the reference dataset.

    Parameters:
    model (pd.DataFrame): DataFrame containing CpGs and their associated weights for the given model.
                         The DataFrame must have columns 'CpG' and 'Weight'.
    ref_data (pd.DataFrame): DataFrame containing the reference dataset with sample beta values.
    meta (pd.DataFrame): DataFrame containing metadata with an 'age' column containing sample ages for computing correlations.

    Returns:
    pd.DataFrame: DataFrame containing the model CpGs, model weights, age-correlations (r), t-statistics (t),
                  and R-squared values (R2) for each CpG.
    list: List of CpG sites present in the model but missing from the reference dataset.
    """

    # Get the intersection of the CpGs between the model and the reference data
    intersect = list(set(ref_data.columns) & set(model.CpG))
    
    # Identify missing CpGs and sort them
    missing = sorted(list(set(model.CpG) - set(intersect)))
    
    # Sort the intersection to keep the lists synced
    intersect.sort()
    
    # Filter the model data to only include CpGs in the intersection
    data = model.loc[model.CpG.isin(intersect)]
    
    # Extract the CpG values from the reference data for the intersection
    combined = ref_data[intersect]
    
    # Compute age-correlations and standard errors
    model_rs, stderrs = get_stats(combined, meta)
    
    # Compute the feature importances based on t-statistics
    importances = get_tvals(model.Weight.tolist(), stderrs)
    
    # Create a DataFrame with the results
    cg_corrs = pd.DataFrame({
        'CpG': combined.columns.tolist(),
        'Weight': model.Weight.tolist(),
        'r': model_rs,
        't': importances
    })
    cg_corrs['R2'] = cg_corrs.r ** 2 
    
    return cg_corrs, missing

def normalized_importance(data):

    """
    This function calculates the normalized importances for the feature selection of a model.

    Parameters:
    data (pd.DataFrame): The output dataframe from the model_corrs function, containing a column "t" with t-statistics for features.

    Returns:
    pd.Series: Series of normalized feature importances, with the same index as the input DataFrame.

    """
    
    importances = abs(data.t)/abs(data.t).max()
    
    return importances


def het_r(data, model, ages):
    """
    Measure the noise (heteroscedasticity) with age for a given predictor by calculating the residuals 
    for the age-correlation and then regressing those residuals on age.

    Parameters:
    data (pd.DataFrame): Processed beta values for the CpG selection of a given model (e.g., Hannum, PhenoAge, DunedinPACE, etc.).
    model (pd.DataFrame): DataFrame containing CpGs and their associated weights for the given model.
                         The DataFrame must have columns 'CpG' and 'Weight'.
    ages (list): List of sample ages corresponding to the beta values in `data`.

    Returns:
    list: List of R-squared values for the correlation between age and noise for each CpG in the given model.
    """
    
    # Get the intersection of the CpGs between the model and the data
    intersect = list(set(data.columns) & set(model.CpG))
    
    # Sort the intersection to keep the lists synced
    intersect.sort()
    
    temp_data = data[intersect]
    het_rs = []
    
    for cg in temp_data.columns:
        # Regress a given predictor on age
        regression = stats.linregress(ages.astype(float), temp_data[cg].tolist())
        slope, intercept, rvalue, pvalue, stderr = regression
        
        preds = ages * slope + intercept
        actuals = temp_data[cg].tolist()
        
        # Calculate the absolute residuals
        abs_resids = abs(preds - actuals)
        
        # Regress the residuals for the predictor on age
        regression = stats.linregress(ages.astype(float), abs_resids)
        slope, intercept, rvalue, pvalue, stderr = regression
        
        het_rs.append(rvalue * rvalue)
        
    return het_rs


def u_test(model, data1, data2):
    
    """
    Perform the Mann-Whitney U test on the beta values of two different sample groups 
    for a model's selected CpGs.

    This function computes the U statistic, p-value, and the negative logarithm (base 10) 
    of the p-value for each CpG site listed in the model, excluding the intercept. 
    It uses the Mann-Whitney U test, a nonparametric test for assessing whether two 
    independent samples come from the same distribution.

    Parameters:
    -----------
    model : object
        A model object that contains the following attribute:
        - `CpG`: a list of CpG site names, where the first element is typically 'Intercept' 
          and the rest are CpG site identifiers.
          
    data1 : pandas.DataFrame
        A DataFrame containing the beta values for the first group of samples. Each row 
        represents a sample, and each column represents a CpG site.
        
    data2 : pandas.DataFrame
        A DataFrame containing the beta values for the second group of samples. Each row 
        represents a sample, and each column represents a CpG site.

    Returns:
    --------
    stats : list
        A list of U statistics, one for each CpG site in the model (excluding the intercept).
    
    p_vals : list
        A list of p-values corresponding to each U statistic.
    
    log_p : list
        A list of the negative logarithm (base 10) of each p-value.

    Notes:
    ------
    - The intercept (first CpG in the model) is excluded from the analysis.
    - The Mann-Whitney U test is a nonparametric test, making it suitable for comparing 
      distributions without assuming normality.
    
    """
        
    from scipy.stats import mannwhitneyu
    from math import log10
    # Perform the Mann-Whitney U test
    p_vals=[]
    stats =[]
    log_p=[]
    
    for cg in model.CpG[1:]:

        
        stat, p = mannwhitneyu(data1[cg].astype(float), data2[cg].astype(float))
        
        log_p += [-log10(p)]
        stats+=[stat]
        p_vals +=[p]
        
    return stats, p_vals, log_p
