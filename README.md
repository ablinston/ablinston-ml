# ablinston-ml

The shared library that sits underneath my machine learning projects. Scraping, feature
engineering, experiment tracking and model diagnostics, pulled out of individual projects so I
stop rewriting the same things.

It is not on PyPI and it is not really aimed at anyone else, but it is a proper installable
package rather than a folder of scripts I copy between repos.

Requires Python 3.11 or later.

## Installing

To work on it:

    pip install -e .

From another project:

    pip install git+https://github.com/ablinston/ablinston-ml

Either of those gets the core dependencies only, which is numpy, pandas, polars and zstandard.
That covers `features.py`, `data.py`, `validation.py` and `utils.py`.

The heavier things sit behind extras, so a project that just wants the feature helpers does not
end up installing a browser driver:

- `modelling` xgboost, scikit-learn, scipy, hyperopt, mlflow, shap, matplotlib and seaborn
- `monitoring` evidently and whylogs
- `scraping` beautifulsoup4, requests and undetected-chromedriver
- `betfair` betfairlightweight and orjson

Ask for them by name:

    pip install "ablinston-ml[modelling] @ git+https://github.com/ablinston/ablinston-ml"

They stack, so `[modelling,scraping]` works, and `[all]` pulls in every group.

Nothing warns you at install time if you skip one. The module fails to import when you first
reach for it, the same way pandas behaves if you read a parquet file without pyarrow.

## What is in it

- `features.py` rolling and time decayed aggregates by group and date, and converting bookmaker
  odds into true probabilities
- `data.py` reading and appending compressed zstd files, which is how I store anything large
- `scraping.py` fetching pages with requests, falling back to a real browser when a site blocks
  that, plus running scrapes in parallel
- `betfair.py` turning Betfair historic stream files into dataframes
- `experiments.py` mlflow run lookups, hyperopt trial persistence, SHAP feature importance and
  probability calibration
- `validation.py` fold assignment for cross validation where the same competitor turns up in many
  rows
- `monitoring.py` logging dataframe profiles to whylogs or Evidently and reading the history back
- `utils.py` odds and ends

To import a function from a module, use `from ablinston_ml.experiments import TemperatureScaler` 
and ensure that modules optional dependencies are installed.

## Why it looks like this

**Flat modules.** The whole package is about twenty five functions. Subpackages holding one or two
files each would be more structure than that amount of code justifies, and it would turn every
import into `ablinston_ml.scraping.scraping`. If a group grows past a handful of modules I will
split it then.

It was one file per function before, which meant a lot of files containing one short function and
a separate import line for each of them.

**`experiments.py` pulls in a lot.** It is by far the heaviest module, ten third party packages
between mlflow, hyperopt, shap, xgboost, sklearn and the plotting libraries. They live together
because I use them together: a modelling run in my projects means fitting with xgboost, tracking
it in mlflow, searching parameters with hyperopt, then looking at SHAP values and calibrating the
output probabilities. Splitting that into four modules would mean four import lines at the top of
every training script and no real gain, since I would be installing all four anyway.

The cost is that someone who only wants the temperature scaler still installs shap and mlflow.
Keeping the whole module behind the `modelling` extra at least means nobody pays for it unless
they ask.

**`src/` layout.** The package lives in `src/` so the only way to import it is to install it. With
the code at the repo root, anything run from that directory imports it straight off the working
directory whether or not it was installed properly, so a broken build can still look fine
locally.

**`monitoring.py` covers two backends.** whylogs and Evidently do the same job here, writing a
profile of a dataframe and reading the history back, so they sit in one module rather than two
files named after the libraries they wrap. Naming modules after the library inside them also
invites shadowing, which is how you end up with a local `mlflow.py` quietly beating the real one.

## Rough edges

Being honest about what is not finished:

- Some functions drop into `pdb` on unexpected input. That suits how I work interactively but it
  is wrong in a library, where it hangs whatever is calling you. They are being replaced with
  raised exceptions.
- Diagnostics go to `print()` rather than `logging`, so the caller has no say in where they go.
- Tests cover two functions in `features.py`, the ones where the maths was fiddly enough to be
  worth pinning down. The rest are untested.
- Every version floor comes from the environment I actually run this in, apart from `evidently`,
  which has no floor because I have not checked which version I last used it with.
