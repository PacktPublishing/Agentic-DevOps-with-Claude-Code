# ABOUTME: Asserts every vendored chart tarball is the version components.yaml pins.
# ABOUTME: A vendored chart that does not match its pin installs a version nobody declared.
#
# Two separate failures motivate this. The vendor script pointed at `platform/` when the tree had
# moved to `solution/platform/`, so it matched zero Applications, vendored nothing and exited 0;
# the tarballs in the repo were whatever had been left behind. And the Tempo tarball sat at 2.2.3
# against a 1.25.0 pin for long enough to ship in a tag. Neither is visible without opening the
# archives, which is what this does.
import glob
import os
import tarfile

import pytest

yaml = pytest.importorskip("yaml")

from conftest import REPO_ROOT

VENDOR_DIR = os.path.join(REPO_ROOT, "charts-vendor")


def _components():
    with open(os.path.join(REPO_ROOT, "components.yaml")) as handle:
        return yaml.safe_load(handle)["components"]


def _vendored():
    """Return {tarball_basename: (chart_name, chart_version)} read from each archive's Chart.yaml."""
    found = {}
    for path in sorted(glob.glob(os.path.join(VENDOR_DIR, "*.tgz"))):
        with tarfile.open(path) as tar:
            for member in tar.getmembers():
                # The chart's own Chart.yaml sits one level down; a subchart's is deeper.
                if member.name.count("/") == 1 and member.name.endswith("/Chart.yaml"):
                    chart = yaml.safe_load(tar.extractfile(member).read())
                    found[os.path.basename(path)] = (chart["name"], str(chart["version"]))
                    break
    return found


def test_charts_are_vendored_at_all():
    """An empty or near-empty vendor directory means the vendor script did nothing."""
    vendored = _vendored()
    assert len(vendored) >= 20, (
        f"only {len(vendored)} charts vendored; scripts/vendor-charts.sh has silently matched "
        "nothing before, so this is a floor rather than a formality"
    )


def _charts_argocd_syncs():
    """Return the chart names Argo CD installs from an Application.

    This is the set that must be on disk. Two pinned charts are deliberately not in it and must
    not be: argo-cd is installed by the bootstrap before GitOps exists, and aws-ebs-csi-driver is
    an EKS managed add-on wired by Terraform in the cluster module, not a Helm
    release in the cluster. Checking components.yaml instead of the Applications would report both
    as defects forever, and a test that always fails gets deleted rather than fixed.
    """
    import glob as _glob

    charts = set()
    pattern = os.path.join(REPO_ROOT, "solution", "platform", "**", "*.yaml")
    for path in _glob.glob(pattern, recursive=True):
        with open(path) as handle:
            try:
                docs = list(yaml.safe_load_all(handle))
            except yaml.YAMLError:
                continue
        for doc in docs:
            if isinstance(doc, dict) and doc.get("kind") == "Application":
                chart = (doc.get("spec", {}).get("source", {}) or {}).get("chart")
                if chart:
                    charts.add(chart)
    return charts


def test_every_chart_argocd_syncs_is_vendored():
    """Nothing may wait on the network at sync time, so every synced chart must be on disk."""
    vendored_names = {name for name, _ in _vendored().values()}
    missing = sorted(_charts_argocd_syncs() - vendored_names)
    assert not missing, f"charts an Application installs with no vendored tarball: {missing}"


def test_the_two_unvendored_pins_are_the_expected_ones():
    """Guard the exemption itself, so a third unvendored chart cannot appear unnoticed.

    Named rather than counted: if a component stops being bootstrap-installed or add-on-installed,
    this fails and someone decides deliberately instead of the gap widening in silence.
    """
    vendored_names = {name for name, _ in _vendored().values()}
    unvendored = {
        c["chart_name"] for c in _components()
        if c.get("chart_name") and c["chart_name"] not in vendored_names
    }
    assert unvendored == {"argo-cd", "aws-ebs-csi-driver"}, (
        f"unvendored pinned charts changed: {sorted(unvendored)}. argo-cd is installed by the "
        "bootstrap and aws-ebs-csi-driver is an EKS managed add-on; anything else here is a gap."
    )


def test_every_vendored_chart_matches_its_pin():
    """A vendored tarball must be the version components.yaml declares.

    CRD sibling charts (`<chart>-crds`, `<chart>-crd`) are not separate components; they are
    released in lockstep with their parent, so they are checked against the parent's pin.
    """
    pins = {c["chart_name"]: str(c["chart_version"]) for c in _components() if c.get("chart_name")}

    mismatches, unknown = [], []
    for tarball, (name, version) in _vendored().items():
        pin = pins.get(name)
        if pin is None:
            parent = None
            for suffix in ("-crds", "-crd"):
                if name.endswith(suffix):
                    stem = name[: -len(suffix)]
                    parent = pins.get(stem) or next(
                        (v for k, v in pins.items() if k.startswith(stem)), None
                    )
                    break
            if parent is None:
                unknown.append(f"{tarball} (chart {name}) is vendored but nothing pins it")
                continue
            pin = parent
        if version != pin:
            mismatches.append(f"{tarball}: Chart.yaml says {version}, components.yaml pins {pin}")

    assert not mismatches, "\n".join(mismatches)
    assert not unknown, "\n".join(unknown)
