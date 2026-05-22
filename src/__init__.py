# Changed: export solver entry points from the package root.
# Why: evaluators may call `from src import Solver`, so the package must expose Solver/predict/predict_one.
from .solver import Solver, predict, predict_one

__all__ = ["Solver", "predict", "predict_one"]
