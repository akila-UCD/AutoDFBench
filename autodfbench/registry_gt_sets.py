# autodfbench/registry_gt_sets.py
"""
Windows registry ground-truth sets.

1.0 is the set used for the AutoDFBench 1.0 paper (Data/windows_registry). A later set lists only the
CSVs it replaces, in its own folder next to Data/windows_registry; every other test case keeps its 1.0 file.
Sets after 1.0 are built with tools/build_registry_gt.py.
"""
from pathlib import Path

DEFAULT_GT_SET = "1.0"

GT_SETS = {
    "1.0": {"folder": "windows_registry", "files": set()},
    "1.1": {
        "folder": "windows_registry_v1.1",
        "files": {
            "[mr]-08_v13.hive.csv",    # key loop: each key listed once (1.0 kept going round the loop)
            "[mr]-08_v15.hive.csv",
            "[nr]-03-3_v13.hive.csv",  # deep key chain: cut off 512 levels below the root (1.0 stopped at 987)
        },
    },
}


def resolve_gt_file(registry_dir, gt_file_name, gt_set=DEFAULT_GT_SET):
    """Path of a ground-truth CSV in the given set: the set's own file if it replaces one, else the 1.0 file."""
    gt_set = str(gt_set or DEFAULT_GT_SET).strip()
    if gt_set not in GT_SETS:
        raise ValueError(f"Unknown ground-truth set {gt_set}; available: {', '.join(GT_SETS)}")
    registry_dir = Path(registry_dir)
    if gt_file_name in GT_SETS[gt_set]["files"]:
        path = registry_dir.parent / GT_SETS[gt_set]["folder"] / gt_file_name
        if not path.exists():
            raise ValueError(f"Ground truth file not found: {GT_SETS[gt_set]['folder']}/{gt_file_name} "
                             f"(build ground-truth set {gt_set} with tools/build_registry_gt.py)")
        return path
    path = registry_dir / gt_file_name
    if not path.exists():
        raise ValueError(f"Ground truth file not found: {gt_file_name}")
    return path
