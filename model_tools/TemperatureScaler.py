import numpy as np
from scipy.optimize import minimize
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.metrics import log_loss
from scipy.special import softmax, expit  # expit = sigmoid

class TemperatureScaler(BaseEstimator, ClassifierMixin):

    def __init__(self, base_model):
        self.base_model = base_model
        self.T_ = None
        
    def _loss(self, T, logits, y_true):
	    T = T[0]
	    scaled_logits = logits / T

	    if scaled_logits.ndim == 1:
	        # Binary classification
	        probs = expit(scaled_logits)
	        probs = np.vstack([1 - probs, probs]).T
	    else:
	        # Multi-class
	        probs = softmax(scaled_logits, axis=1)

	    # Compute negative log-likelihood using sklearn
	    nll = log_loss(y_true, probs)
	    return nll

	# -----------------------
    # Fit the temperature parameter on a validation set
    def fit(self, X_val, y_val):
    	
        """
        Fit temperature scaler on validation data.
        X_val: feature matrix
        y_val: true labels
        """
        # Get raw logits from the base model
        logits = self.base_model.predict(X_val, output_margin=True)

        # Optimize T
        res = minimize(
            self._loss,
            x0=np.array([1.0]),
            args=(logits, y_val),
            bounds=[(1e-2, 100)],
            method="L-BFGS-B"
        )
        self.T_ = res.x[0]
        return self

    def predict_proba(self, X):
        # Get raw logits from the model
        logits = self.base_model.predict(X, output_margin=True)
        scaled = logits / self.T_

        if scaled.ndim == 1:
            probs = expit(scaled)
            return np.vstack([1 - probs, probs]).T

        return softmax(scaled, axis=1)

    def predict(self, X):
        return np.argmax(self.predict_proba(X), axis=1)