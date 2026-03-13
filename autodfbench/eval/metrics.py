# autodfbench/metrics.py

def _div(n, d):
    return (n / d) if d else 0.0

def compute_metrics(tp: int, fp: int, fn: int):
    precision = _div(tp, tp + fp)
    recall = _div(tp, tp + fn)
    f1 = _div(2 * precision * recall, precision + recall)
    return precision, recall, f1
