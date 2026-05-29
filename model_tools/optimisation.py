import pickle
from hyperopt import Trials, fmin, tpe

class PersistingTrials(Trials):
    def __init__(self, save_path, *args, **kwargs):
        self.save_path = save_path
        super().__init__(*args, **kwargs)
    def refresh(self):
        super().refresh()
        with open(self.save_path, "wb") as f:
            pickle.dump(self, f)
