import numpy as np
import pandas as pd
import pdb
import matplotlib.pyplot as plt
import seaborn as sns
import shap
import xgboost as xgb

def feature_shap_rf(X_train, y_train, trees = 1000, output_path = ''):
    """
    This function fits a random forest to a data frame then returns the SHAP importance
    of all the features included
    
    :param X_train: pandas data frame of all the predictors
    :param y_train: pandas series of the variable to be predicted
    :param trees: the number of trees to fit the random forest with
    """
    # pdb.set_trace()
    
    # Set the parameters for the model
    params = {
        'nthread': 3, # Only applies to CPU cores
        'booster': 'gbtree',
        'num_boost_round': 1, # to tell the package to train only 1 random forest
        'colsample_bynode': np.sqrt(len(X_train.columns)) / len(X_train.columns), # fraction of columns to select for each tree
        'num_parallel_tree': trees, # the size of the forest. For 16k features, and choosing sqrt, 2500 gives 99.998% chance all features selected at least once
        'learning_rate': 1, # Learning rate
        'min_child_weight': 15,                 # The min observations that should be left in a leaf node    
        'subsample': 0.85,
        # 'max_depth': 6,
        'max_bin': 175, # used in the hist method to speed up, this says how many bins the vars should be split into
        'objective': 'multi:softprob', # Multi classification objective
        'eval_metric': 'mlogloss',       # Evaluation metric
        'tree_method': 'hist',      # Use GPU accelerated algorithm
        'device': 'cuda',           # Use CUDA / GPU
        'predictor': 'gpu_predictor',   # Use GPU for prediction
        'verbosity': 1,
        'num_class': len(y_train.unique()),
        'random_state': 38
    }

    # 1. Define your mapping
    mapping = {"home": 0, "away": 1, "draw": 2}
    
    # 2. Convert the column to integers
    y_train_numeric = y_train.replace(mapping)
    
    # 3. Now it works
    train = xgb.DMatrix(X_train, label=y_train_numeric)
    
    # Train the model
    rf_model = xgb.train(params, train)

    # Get feature importance scores
    importance = rf_model.get_score(importance_type='total_gain')

    # Sort features by importance
    sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    # TreeSHAP calculation
    explainer = shap.TreeExplainer(rf_model)
    shap_values = explainer.shap_values(X_train)
    # shap_values3 = rf_model.predict(train, pred_contribs=True)
        
    # Assuming `shap_values` has the shape (6792, 18000, 3)
    # Take the mean absolute SHAP values across all samples and classes
    mean_shap_values = np.mean(np.abs(shap_values), axis=(0, 2))
    
    # Create a DataFrame for better readability
    shap_importance_df = pd.DataFrame({'Feature': X_train.columns, 'Mean SHAP Value': mean_shap_values})
    
    # Sort features by importance
    shap_importance_df = shap_importance_df.sort_values(by='Mean SHAP Value', ascending=False).reset_index(drop=True)
    
    # # Display or save the table
    # print(shap_importance_df.head(10))  # Shows the top 10 most important features
    if output_path != '':
        # Optionally, save to CSV
        shap_importance_df.to_csv(output_path + '/shap_feature_importance.csv', index=False)

    return shap_importance_df


def shaps_chart(shaps):
    """
    This function takes the shaps output from feature_shap_rf() and converts it into a chart
    The features need to be named with parameters embedded within, separated by "|" for this to work
    
    :param shaps: output from feature_shap_rf()
    """

    pdb.set_trace()
    
    # Separate the features by |
    values = shaps['Feature'].str.split('|')

    if len(values[0]) == 3:
        param1 = values.apply(lambda x: x[1])
        
        #tbc
    else:
        param1 = values.apply(lambda x: x[1]).astype('float64')
        param2 = values.apply(lambda x: x[3]).astype('float64')
        
        # Create the data frame for the heatmap. Drop duplicates because there will be home and away in there. Take the highest
        df = pd.DataFrame({'1st_param': param1, '2nd_param': param2, 'values': shaps['Mean SHAP Value']}).drop_duplicates(subset = ['1st_param', '2nd_param'])
        
        # 2. Pivot the data to create a matrix
        # If you have duplicate (x,y) pairs, use .pivot_table(aggfunc='mean') instead
        pivot_table = df.pivot(index='2nd_param', columns='1st_param', values='values')
        
        # 3. Plot
        plt.figure(figsize=(10, 8))
        plot = sns.heatmap(pivot_table, annot=True, fmt='.2f')

    return plot