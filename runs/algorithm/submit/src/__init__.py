# Changed: expose the submission package without importing heavy runtime dependencies.
# Why: evaluator entrypoints may import from package root instead of src.solver directly.
from src.solver import Solver, StatefulOpalVerifier, predict, predict_one

__all__ = ["Solver", "StatefulOpalVerifier", "predict", "predict_one"]
